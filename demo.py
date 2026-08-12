# Demo Gauntlet — pilot match. Two Gray-Scott reaction-diffusion demos, one theme.
# Every pixel and every audio sample comes from code. numpy + stdlib + ffmpeg only.
# Usage: python demo.py [a|b|all] [--preview] [--selftest]
import argparse, os, struct, subprocess, sys, wave
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FPS = 30
DUR_S = 28
SIM_W, SIM_H = 480, 270
OUT_W, OUT_H = 960, 540
SR = 44100
PENTA = [0, 3, 5, 7, 10, 12, 15, 17, 19, 22]  # minor pentatonic, 2 octaves

CONFIGS = {
    "a": dict(
        name="coral", feed=0.0545, kill=0.062, steps_per_frame=30, seed=11,
        n_seeds=7, seed_style="squares",
        # IQ cosine palette: deep ocean blue -> warm coral
        pal_a=(0.45, 0.35, 0.30), pal_b=(0.45, 0.35, 0.35),
        pal_c=(1.0, 1.0, 1.0), pal_d=(0.60, 0.45, 0.30),
        drone_hz=110.0, pluck_root_hz=220.0,
    ),
    "b": dict(
        # ponytail: isolated spots are sub-critical in this regime and dissolve;
        # mitosis needs neighbor interaction, so seed densely (>=36 on 480x270).
        name="mitosis", feed=0.0367, kill=0.0649, steps_per_frame=20, seed=7,
        n_seeds=48, seed_style="spots",
        # near-black -> peach-pink -> violet
        pal_a=(0.50, 0.30, 0.45), pal_b=(0.50, 0.40, 0.45),
        pal_c=(0.7, 0.8, 0.7), pal_d=(0.55, 0.50, 0.40),
        drone_hz=82.41, pluck_root_hz=164.81,
    ),
}


def laplacian(Z):
    return (-Z
            + 0.2 * (np.roll(Z, 1, 0) + np.roll(Z, -1, 0)
                     + np.roll(Z, 1, 1) + np.roll(Z, -1, 1))
            + 0.05 * (np.roll(Z, (1, 1), (0, 1)) + np.roll(Z, (1, -1), (0, 1))
                      + np.roll(Z, (-1, 1), (0, 1)) + np.roll(Z, (-1, -1), (0, 1))))


def init_grid(cfg, rng):
    u = np.ones((SIM_H, SIM_W))
    v = np.zeros((SIM_H, SIM_W))
    for _ in range(cfg["n_seeds"]):
        cy = rng.integers(20, SIM_H - 20)
        cx = rng.integers(30, SIM_W - 30)
        if cfg["seed_style"] == "squares":
            v[cy - 4:cy + 4, cx - 4:cx + 4] = 1.0
            u[cy - 4:cy + 4, cx - 4:cx + 4] = 0.5
        else:
            yy, xx = np.ogrid[:SIM_H, :SIM_W]
            m = (yy - cy) ** 2 + (xx - cx) ** 2 < 25
            v[m] = 1.0
            u[m] = 0.5
    v += rng.uniform(0, 0.02, v.shape)
    return u, v


def step(u, v, f, k):
    uvv = u * v * v
    u += 1.0 * laplacian(u) - uvv + f * (1.0 - u)
    v += 0.5 * laplacian(v) + uvv - (f + k) * v
    np.clip(u, 0, 1, out=u)
    np.clip(v, 0, 1, out=v)


def colorize(v, cfg):
    t = np.clip((v - 0.05) / 0.30, 0.0, 1.0)
    t = t * t * (3 - 2 * t)  # smoothstep for softer edges
    rgb = np.empty((SIM_H, SIM_W, 3))
    for ch in range(3):
        rgb[..., ch] = cfg["pal_a"][ch] + cfg["pal_b"][ch] * np.cos(
            2 * np.pi * (cfg["pal_c"][ch] * t + cfg["pal_d"][ch]))
    return (np.clip(rgb, 0, 1) * 255).astype(np.uint8)


def run_sim(cfg, n_frames, frame_sink):
    """Run the sim. Call frame_sink(i, rgb) per frame. Return per-frame stats."""
    rng = np.random.default_rng(cfg["seed"])
    u, v = init_grid(cfg, rng)
    acts, cxs = [], []
    xs = np.arange(SIM_W)
    for i in range(n_frames):
        for _ in range(cfg["steps_per_frame"]):
            step(u, v, cfg["feed"], cfg["kill"])
        acts.append(float(v.sum()))
        w = v.sum(0)
        cxs.append(float((w * xs).sum() / max(w.sum(), 1e-9)) / SIM_W)
        frame_sink(i, colorize(v, cfg))
    assert np.isfinite(u).all() and np.isfinite(v).all(), "sim went non-finite"
    return np.array(acts), np.array(cxs)


# ---------- audio ----------

def karplus_strong(freq, dur, sr, rng, decay=0.996):
    n_buf = max(2, int(sr / freq))
    buf = rng.uniform(-1, 1, n_buf)
    n = int(dur * sr)
    chunks, total = [], 0
    while total < n:
        chunks.append(buf.copy())
        buf = decay * 0.5 * (buf + np.roll(buf, -1))
        total += n_buf
    return np.concatenate(chunks)[:n]


def make_audio(cfg, acts, cxs, n_frames):
    dur = n_frames / FPS
    n = int(dur * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(cfg["seed"] + 1000)

    # activity envelope, smoothed, resampled to audio rate
    env = acts / max(acts.max(), 1e-9)
    kern = np.ones(15) / 15
    env = np.convolve(env, kern, mode="same")
    env_a = np.interp(t, np.arange(n_frames) / FPS, env)

    # drone: band-limited saw-ish stack of sines, two voices detuned, 5th below
    drone = np.zeros(n)
    for f0 in (cfg["drone_hz"] * 0.997, cfg["drone_hz"] * 1.003):
        for h in range(1, 7):
            drone += np.sin(2 * np.pi * f0 * h * t + rng.uniform(0, 6.28)) / h
    drone += 0.6 * np.sin(2 * np.pi * cfg["drone_hz"] * 1.5 * t)
    drone *= (0.30 + 0.45 * env_a) * (1 + 0.15 * np.sin(2 * np.pi * 0.13 * t))
    drone /= np.abs(drone).max()

    # plucks: triggered by activity-change spikes, pitch from spatial centroid x
    d_act = np.abs(np.diff(env, prepend=env[0]))
    thresh = np.percentile(d_act, 70)
    left = np.zeros(n)
    right = np.zeros(n)
    last = -100
    for i in range(n_frames):
        if d_act[i] >= thresh and i - last >= 8:  # min spacing ~0.27 s
            last = i
            note = PENTA[int(np.clip(cxs[i], 0, 0.999) * len(PENTA))]
            fq = cfg["pluck_root_hz"] * 2 ** (note / 12)
            p = karplus_strong(fq, 1.6, SR, rng) * 0.5
            s = int(i / FPS * SR)
            e = min(s + len(p), n)
            pan = cxs[i]  # 0 = left, 1 = right
            left[s:e] += p[:e - s] * (1 - 0.7 * pan)
            right[s:e] += p[:e - s] * (0.3 + 0.7 * pan)

    mix_l = 0.55 * drone + 0.45 * left
    mix_r = 0.55 * drone + 0.45 * right
    peak = max(np.abs(mix_l).max(), np.abs(mix_r).max(), 1e-9)
    mix_l, mix_r = mix_l / peak * 0.85, mix_r / peak * 0.85
    fade = np.minimum(1, np.minimum(t, dur - t))  # 1 s fade in/out
    mix_l *= fade
    mix_r *= fade
    return mix_l, mix_r


def write_wav(path, left, right):
    data = np.empty(2 * len(left), dtype=np.int16)
    data[0::2] = (left * 32767).astype(np.int16)
    data[1::2] = (right * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


# ---------- pipelines ----------

def ff(*args):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def render(key, preview=False):
    cfg = CONFIGS[key]
    name = cfg["name"]
    n_frames = FPS * DUR_S
    print(f"[{name}] simulating {n_frames} frames "
          f"({cfg['steps_per_frame']} steps/frame)...", flush=True)

    if preview:
        marks = {int(n_frames * p) - 1 for p in (0.25, 0.5, 0.75, 1.0)}

        def sink(i, rgb):
            if i in marks:
                png = os.path.join(HERE, f"preview_{name}_{i:03d}.png")
                p = subprocess.run(
                    ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo",
                     "-pix_fmt", "rgb24", "-s", f"{SIM_W}x{SIM_H}", "-i", "-",
                     "-frames:v", "1", png], input=rgb.tobytes())
                p.check_returncode()
        run_sim(cfg, n_frames, sink)
        print(f"[{name}] preview PNGs written")
        return

    vid_tmp = os.path.join(HERE, f"_{name}_video.mp4")
    wav_tmp = os.path.join(HERE, f"_{name}_audio.wav")
    out = os.path.join(HERE, f"{name}.mp4")
    enc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo",
         "-pix_fmt", "rgb24", "-s", f"{SIM_W}x{SIM_H}", "-r", str(FPS), "-i", "-",
         "-vf", f"scale={OUT_W}:{OUT_H}:flags=lanczos",
         "-c:v", "libx264", "-crf", "18", "-preset", "medium",
         "-pix_fmt", "yuv420p", vid_tmp], stdin=subprocess.PIPE)
    acts, cxs = run_sim(cfg, n_frames, lambda i, rgb: enc.stdin.write(rgb.tobytes()))
    enc.stdin.close()
    assert enc.wait() == 0, "video encode failed"

    print(f"[{name}] synthesizing audio...", flush=True)
    left, right = make_audio(cfg, acts, cxs, n_frames)
    write_wav(wav_tmp, left, right)

    ff("-i", vid_tmp, "-i", wav_tmp, "-c:v", "copy", "-c:a", "aac",
       "-b:a", "192k", "-shortest", out)
    ff("-i", out, "-lavfi", f"showspectrumpic=s={OUT_W}x{OUT_H}:legend=1",
       os.path.join(HERE, f"{name}_spectrogram.png"))
    for sec in (4, 12, 20, 27):
        ff("-ss", str(sec), "-i", out, "-frames:v", "1",
           os.path.join(HERE, f"{name}_frame_{sec:02d}s.png"))
    os.remove(vid_tmp)
    os.remove(wav_tmp)
    print(f"[{name}] done -> {out}")


def selftest():
    for key, cfg in CONFIGS.items():
        rng = np.random.default_rng(cfg["seed"])
        u, v = init_grid(cfg, rng)
        for _ in range(50):
            step(u, v, cfg["feed"], cfg["kill"])
        assert np.isfinite(u).all() and np.isfinite(v).all(), f"{key}: non-finite"
        assert v.std() > 1e-6, f"{key}: sim flatlined"
    p = karplus_strong(220.0, 0.5, SR, np.random.default_rng(0))
    assert len(p) == int(0.5 * SR) and np.isfinite(p).all()
    print("selftest OK")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("which", nargs="?", default="all", choices=["a", "b", "all"])
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        sys.exit(0)
    for k in (["a", "b"] if args.which == "all" else [args.which]):
        render(k, preview=args.preview)
