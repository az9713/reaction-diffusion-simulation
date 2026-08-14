# Stage 1 of PLAN.html — the f-k contact sheet for the Gray-Scott solver in demo.py.
# demo.py is not modified; it is imported only as the reference the selftest checks.
# Usage: python sweep.py --selftest        # batched stepper vs demo.step, seconds
#        python sweep.py --stage1          # 12x12 sheet + 2 calibration tiles, ~20 min
import argparse, os, subprocess, sys, time
import numpy as np
from scipy.ndimage import convolve
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
KERN = np.array([[.05, .2, .05], [.2, -1., .2], [.05, .2, .05]])  # == demo.laplacian
N = 12
F_RANGE = (0.010, 0.090)   # rows
K_RANGE = (0.045, 0.070)   # columns
CAL = [(0.0545, 0.0620, "coral"), (0.0367, 0.0649, "mitosis")]  # ground-truth tiles
DYN = 1e-4                 # mean |dv|/px/step above this = dynamic. Heuristic cutoff.


# ---------- batched stepper ----------

def make_buffers(shape, dtype):
    return [np.empty(shape, dtype) for _ in range(3)]


def step_batch(u, v, f, k, Du, Dv, kern3, buf, check=False, clip=True):
    """One Euler step on a (T,H,W) stack. Same term order as demo.step:63-68.

    f and k are (T,1,1) in the stack's dtype. Returns the per-tile pre-clip max
    when check=True, else None. kern3 is size 1 on the leading axis, so the wrap
    convolution cannot bleed between tiles. clip=False drops demo.py's [0,1] clamp,
    which Ready does not have; every stage 1-5 run used clip=True.
    """
    lap, uvv, tmp = buf
    np.multiply(u, v, out=uvv)
    np.multiply(uvv, v, out=uvv)                  # u*v*v, from the old u and v
    convolve(u, kern3, output=lap, mode="wrap")   # u += Du*lap(u) - uvv + f*(1-u)
    np.multiply(lap, Du, out=lap)
    np.subtract(lap, uvv, out=lap)
    np.subtract(1.0, u, out=tmp)
    np.multiply(tmp, f, out=tmp)
    np.add(lap, tmp, out=lap)
    np.add(u, lap, out=u)
    convolve(v, kern3, output=lap, mode="wrap")   # v += Dv*lap(v) + uvv - (f+k)*v
    np.multiply(lap, Dv, out=lap)
    np.add(lap, uvv, out=lap)
    np.multiply(v, f + k, out=tmp)
    np.subtract(lap, tmp, out=lap)
    np.add(v, lap, out=v)
    m = None
    if check:  # PLAN "Known risks": the clip can hide a divergence. Look before clipping.
        m = np.maximum(u.max(axis=(1, 2)), v.max(axis=(1, 2)))
    if clip:
        np.clip(u, 0, 1, out=u)
        np.clip(v, 0, 1, out=v)
    return m


def init_state(T, S, dtype, noise_seed=0):
    """One identical seed in every tile: a central 20 px square plus fixed noise."""
    rng = np.random.default_rng(noise_seed)
    u = np.ones((T, S, S), dtype)
    v = np.zeros((T, S, S), dtype)
    lo, hi = S // 2 - 10, S // 2 + 10
    v[:, lo:hi, lo:hi] = 1.0
    u[:, lo:hi, lo:hi] = 0.5
    v += rng.uniform(0, 0.02, (S, S)).astype(dtype)  # broadcast: same field per tile
    return u, v


# ---------- stage 1 ----------

def run_stage1(size=192, steps=8000, Du=1.0, Dv=0.5, dtype=np.float32):
    fs = np.linspace(*F_RANGE, N)
    ks = np.linspace(*K_RANGE, N)
    FF, KK = np.meshgrid(fs, ks, indexing="ij")
    fv = np.concatenate([FF.ravel(), [c[0] for c in CAL]])
    kv = np.concatenate([KK.ravel(), [c[1] for c in CAL]])
    T = len(fv)
    f = fv.astype(dtype).reshape(T, 1, 1)
    k = kv.astype(dtype).reshape(T, 1, 1)
    kern3 = KERN.astype(dtype)[None]

    u, v = init_state(T, size, dtype)
    buf = make_buffers(u.shape, dtype)
    prev = np.empty_like(v)
    dv_acc = np.zeros(T)
    unstable = np.zeros(T, bool)

    print(f"stage 1: {T} tiles ({N}x{N} grid + {len(CAL)} calibration), "
          f"{size} px, {steps} steps, {np.dtype(dtype).name}", flush=True)
    t0 = time.perf_counter()
    for s in range(steps):
        last50 = s >= steps - 50
        if last50:
            np.copyto(prev, v)
        m = step_batch(u, v, f, k, Du, Dv, kern3, buf, check=(s % 100 == 0))
        if m is not None:
            unstable |= ~(m <= 5.0)  # ~(<=) also catches nan
        if last50:
            dv_acc += np.abs(v - prev).mean(axis=(1, 2), dtype=np.float64)
        if s % 500 == 0 and s:
            el = time.perf_counter() - t0
            print(f"  step {s}/{steps}  {el/s*1000:.0f} ms/step  "
                  f"eta {(steps-s)*el/s/60:.1f} min", flush=True)
    print(f"  done in {(time.perf_counter()-t0)/60:.1f} min", flush=True)

    dv = dv_acc / 50.0
    vsum = v.sum(axis=(1, 2), dtype=np.float64)
    fill = (v > 0.1).mean(axis=(1, 2), dtype=np.float64)
    if unstable.any():
        print(f"WARNING: {int(unstable.sum())} tiles exceeded the pre-clip bound: "
              f"{np.flatnonzero(unstable).tolist()}", flush=True)
    return v, fv, kv, dv, vsum, fill, unstable


# ---------- output ----------

def _font():
    try:
        return ImageFont.load_default(size=13)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def render_grid(v, labels, bars, ncol, path):
    """Tile assembly in numpy, labels through PIL. No new dependency.

    labels[i] = (text, rgb). bars[i] = (fraction 0..1, rgb) or None.
    """
    T, S, W = v.shape                             # W != S only for E1's 128x64 grid
    t = np.clip((v - 0.05) / 0.30, 0.0, 1.0)
    t = t * t * (3 - 2 * t)                       # same ramp as demo.colorize
    gray = (t * 255).astype(np.uint8)
    pad, lab = 3, 17
    cw, ch = W + pad, S + lab + pad
    rows = -(-T // ncol)
    img = Image.new("RGB", (ncol * cw + pad, rows * ch + pad), (16, 16, 20))
    d = ImageDraw.Draw(img)
    font = _font()
    for i in range(T):
        r, c = divmod(i, ncol)
        x, y = pad + c * cw, pad + r * ch
        img.paste(Image.fromarray(np.dstack([gray[i]] * 3)), (x, y))
        d.text((x + 1, y + S + 2), labels[i][0], font=font, fill=labels[i][1])
        if bars[i]:
            frac, bc = bars[i]
            d.rectangle([x, y + S + lab - 1, x + max(int(W * frac), 1), y + S + lab],
                        fill=bc)
    img.save(path)
    print(f"wrote {path} ({img.size[0]}x{img.size[1]})")


def sheet_labels(fv, kv, dv, vsum, unstable):
    scale = max(dv.max(), 1e-12)
    labels, bars = [], []
    for i in range(len(fv)):
        name = CAL[i - N * N][2] if i >= N * N else ""
        dead = vsum[i] < 1.0
        col = (255, 90, 90) if unstable[i] else (110, 130, 150) if dead else (230, 225, 210)
        labels.append((f"{name}f{fv[i]:.4f} k{kv[i]:.4f} d{dv[i]:.1e}", col))
        bars.append(None if dead else
                    (dv[i] / scale, (235, 150, 60) if dv[i] > DYN else (90, 170, 120)))
    return labels, bars


def write_table(fv, kv, dv, vsum, fill, unstable, path):
    """Stage 2 reads this: bistable candidates are low-fill, non-dead, settled tiles."""
    lines = ["idx\tf\tk\tmean_dv\tv_sum\tfill\tclass"]
    for i in range(len(fv)):
        dead = vsum[i] < 1.0
        cls = ("unstable" if unstable[i] else "dead" if dead else
               "dynamic" if dv[i] > DYN else "static")
        if not dead and not unstable[i] and fill[i] < 0.35:
            cls += ",bistable?"
        if i >= N * N:
            cls += "," + CAL[i - N * N][2]
        lines.append(f"{i}\t{fv[i]:.5f}\t{kv[i]:.5f}\t{dv[i]:.4e}\t"
                     f"{vsum[i]:.1f}\t{fill[i]:.3f}\t{cls}")
    open(path, "w").write("\n".join(lines) + "\n")
    print(f"wrote {path}")
    print("\n".join(lines[-3:]))  # the two calibration rows land here


# ---------- stage 2: designed seeds inside the bistable window ----------

# The six stage-1 tiles that held one localised structure without filling the domain.
BISTABLE = [(0.060909, 0.063182), (0.068182, 0.063182), (0.075455, 0.060909),
            (0.060909, 0.065455), (0.068182, 0.065455), (0.075455, 0.063182)]
USKATE_F = 0.062          # reported u-skate f, unverified in this parameterisation
USKATE_K = (0.0605, 0.0635)   # stage 1 puts the bistable edge inside this gap
SEED_R = 7


def _disc(S, cy, cx, r):
    yy, xx = np.ogrid[:S, :S]
    return (yy - cy) ** 2 + (xx - cx) ** 2 < r * r


def seed_shapes(S):
    """The four designed seeds of PLAN.html stage 2, as v fields. No noise:
    noise destroys the symmetry these seeds exist to control."""
    c = S // 2
    out = [("single", _disc(S, c, c, SEED_R).astype(np.float64))]
    for g in (2, 4, 6, 8, 12, 16, 22, 30):    # the one real 1-D knob: edge-to-edge gap
        off = SEED_R + g // 2
        out.append((f"pair g{g:02d}",
                    (_disc(S, c, c - off, SEED_R) |
                     _disc(S, c, c + off, SEED_R)).astype(np.float64)))
    out.append(("asym", (_disc(S, c, c, SEED_R) &
                         ~_disc(S, c, c + SEED_R, int(SEED_R * 0.9))).astype(np.float64)))
    out.append(("grad", np.linspace(0.4, 1.0, S)[None, :] * _disc(S, c, c, SEED_R)))
    return out


def _ang(w, cos_t, sin_t):
    """Angle of the weighted centroid on a wrapping axis. w is (T,S).

    A plain centroid jumps when a structure crosses the edge. The circular mean
    does not — and np.unwrap on the angle track then gives true displacement.
    """
    return np.arctan2(w @ sin_t, w @ cos_t)


def run_stage2(size=192, steps=10000, Du=1.0, Dv=0.5, dtype=np.float32, sample=10,
               pairs=None, keep_seeds=None, label="stage 2"):
    """pairs / keep_seeds default to the full stage-2 grid. Restricting them is how
    stages 4 and 5 run their own tiles without paying for the rest."""
    if pairs is None:
        pairs = BISTABLE + [(USKATE_F, kk) for kk in np.linspace(*USKATE_K, 8)]
    seeds = seed_shapes(size)
    if keep_seeds is not None:
        seeds = [s for s in seeds if s[0] in keep_seeds]
    names = [f"{sn} f{pf:.4f} k{pk:.4f}" for pf, pk in pairs for sn, _ in seeds]
    T = len(names)
    v = np.stack([s for _ in pairs for _, s in seeds]).astype(dtype)
    u = np.where(v > 0, 0.5, 1.0).astype(dtype)
    f = np.array([pf for pf, _ in pairs for _ in seeds], dtype).reshape(T, 1, 1)
    k = np.array([pk for _, pk in pairs for _ in seeds], dtype).reshape(T, 1, 1)
    kern3 = KERN.astype(dtype)[None]
    buf = make_buffers(u.shape, dtype)

    th = 2 * np.pi * np.arange(size) / size
    cos_t, sin_t = np.cos(th), np.sin(th)
    nsamp = steps // sample
    ax = np.empty((nsamp, T))
    ay = np.empty((nsamp, T))
    vs = np.empty((nsamp, T))
    fl = np.empty((nsamp, T))   # fill over time: a grower that saturates the torus
    unstable = np.zeros(T, bool)  # flattens v.sum() too, and would read as a glider.

    print(f"{label}: {T} tiles ({len(pairs)} f-k pairs x {len(seeds)} seeds), "
          f"{size} px, {steps} steps", flush=True)
    t0 = time.perf_counter()
    for s in range(steps):
        m = step_batch(u, v, f, k, Du, Dv, kern3, buf, check=(s % 100 == 0))
        if m is not None:
            unstable |= ~(m <= 5.0)
        if s % sample == 0:
            j = s // sample
            vs[j] = v.sum(axis=(1, 2), dtype=np.float64)
            fl[j] = (v > 0.1).mean(axis=(1, 2), dtype=np.float64)
            ax[j] = _ang(v.sum(axis=1, dtype=np.float64), cos_t, sin_t)
            ay[j] = _ang(v.sum(axis=2, dtype=np.float64), cos_t, sin_t)
        if s % 1000 == 0 and s:
            el = time.perf_counter() - t0
            print(f"  step {s}/{steps}  eta {(steps-s)*el/s/60:.1f} min", flush=True)
    print(f"  done in {(time.perf_counter()-t0)/60:.1f} min", flush=True)

    px = np.unwrap(ax, axis=0) * size / (2 * np.pi)   # unwrap: the grid wraps
    py = np.unwrap(ay, axis=0) * size / (2 * np.pi)
    # Full tracks, not their last row: a verdict that throws the trend away cannot be
    # re-judged without paying for the whole run again.
    return v, names, vs, fl, px, py, unstable, sample, len(seeds)


def tail_metrics(vs, px, py, sample, window=2000):
    """Verdict inputs over the final `window` steps: net displacement and flat mass."""
    n2 = window // sample
    disp = np.hypot(px[-1] - px[-n2], py[-1] - py[-n2])
    tail = vs[-n2:]
    flat = (tail.max(0) - tail.min(0)) / np.maximum(tail.mean(0), 1e-9) < 0.02
    return disp, flat


def report_stage2(v, names, vs, fl, px, py, unstable, sample, ncol, path_png, path_txt):
    vsum = vs[-1]
    fill = (v > 0.1).mean(axis=(1, 2), dtype=np.float64)  # from the final v, as before
    disp, flat = tail_metrics(vs, px, py, sample)
    verdicts, labels, bars = [], [], []
    scale = max(disp.max(), 1e-9)
    for i, nm in enumerate(names):
        if unstable[i]:
            vd, col = "unstable", (255, 90, 90)
        elif vsum[i] < 1.0:
            vd, col = "dead", (110, 130, 150)
        elif fill[i] > 0.5:
            vd, col = "grew", (150, 150, 200)
        elif not flat[i]:
            vd, col = "unsettled", (200, 200, 120)
        elif disp[i] > 5.0:
            vd, col = "GLIDER", (255, 140, 40)
        else:
            vd, col = "soliton", (230, 225, 210)
        verdicts.append(vd)
        labels.append((f"{nm} {vd[:4]} {disp[i]:.1f}px", col))
        bars.append(None if vsum[i] < 1.0 else
                    (disp[i] / scale, (255, 140, 40) if vd == "GLIDER" else (90, 170, 120)))
    render_grid(v, labels, bars, ncol, path_png)

    lines = ["name\tv_sum\tfill\tdisp_2000\tverdict"]
    for i, nm in enumerate(names):
        lines.append(f"{nm}\t{vsum[i]:.1f}\t{fill[i]:.3f}\t{disp[i]:.2f}\t{verdicts[i]}")
    open(path_txt, "w").write("\n".join(lines) + "\n")
    print(f"wrote {path_txt}")

    order = np.argsort(-disp)
    print("\ntop 10 by displacement over the final 2000 steps:")
    for i in order[:10]:
        print(f"  {names[i]:28s} {verdicts[i]:9s} disp={disp[i]:6.2f} px  "
              f"v_sum={vsum[i]:7.1f} fill={fill[i]:.3f}")
    n = verdicts.count("GLIDER")
    print(f"\nstage 2: {'PASS' if n else 'FAIL'} — {n} glider(s). "
          + ("" if n else "No moving localised structure survived 2000 steps."))
    for vd in ("soliton", "grew", "dead", "unsettled", "unstable"):
        print(f"  {vd:9s} {verdicts.count(vd)}")


# ---------- stage 4: glider, or a worm that had not finished growing? ----------

# Stage 2's four near-misses, selected by rule from sweep_seeds_r050.txt: asym seed,
# verdict "unsettled", disp > 5 px over the final 2000 steps, fill < 0.35. They failed
# the flat-mass test, not the motion test. k values come from linspace(*USKATE_K, 8).
NEAR_MISS = [(0.060909, 0.063182), (0.062, 0.06307143),
             (0.068182, 0.063182), (0.062, 0.0635)]
FILL_CAP = 0.35     # above this the structure has saturated the torus, so v.sum()
GROW_TOL = 0.02     # flattens for the wrong reason. Mass trend over the 2nd half.


def glider_verdicts(vs, fl, px, py, unstable, sample):
    """The one glider test, shared by stages 4 and 5. Judges the second half only:
    the first half is still transient. A glider holds its mass AND keeps moving."""
    h = len(vs) // 2
    tail = vs[h:]
    grow = (vs[-1] - vs[h]) / np.maximum(vs[h], 1e-9)   # direction, for the label
    # Flatness is a spread, not an endpoint difference: a curve that rises then falls
    # has grow ~ 0 and is not conserved. spread >= |grow|, so this is strictly stronger.
    spread = (tail.max(0) - tail.min(0)) / np.maximum(tail.mean(0), 1e-9)
    speed = np.hypot(px[-1] - px[h], py[-1] - py[h]) / ((len(vs) - 1 - h) * sample) * 1000
    fmax = fl.max(axis=0)
    verdicts = []
    for i in range(vs.shape[1]):
        if unstable[i]:
            vd = "unstable"
        elif vs[-1, i] < 1.0:
            vd = "dead"
        elif fmax[i] > FILL_CAP:
            vd = "worm-filled"      # grew into the torus; flat mass here means nothing
        elif spread[i] > GROW_TOL:
            vd = "worm-growing" if grow[i] > 0 else "decaying"
        elif speed[i] < 0.1:
            vd = "soliton"          # mass settled, but it stopped moving
        else:
            vd = "GLIDER"
        verdicts.append(vd)
    return grow, speed, fmax, verdicts


def report_stage4(v, names, vs, fl, px, py, unstable, sample, ncol, png, txt, npz,
                  label="stage 4"):
    np.savez_compressed(npz, vs=vs, fl=fl, px=px, py=py, sample=sample,
                        names=np.array(names))
    print(f"wrote {npz}")
    t = np.arange(len(vs)) * sample
    grow, speed, fmax, verdicts = glider_verdicts(vs, fl, px, py, unstable, sample)

    lines = ["name\tv_sum_end\tgrow_2nd_half\tfill_max\tspeed_px_per_1k\tverdict"]
    for i, nm in enumerate(names):
        lines.append(f"{nm}\t{vs[-1, i]:.1f}\t{grow[i]:+.4f}\t{fmax[i]:.3f}\t"
                     f"{speed[i]:.3f}\t{verdicts[i]}")
    open(txt, "w").write("\n".join(lines) + "\n")
    print(f"wrote {txt}")
    print("\n".join(lines))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    for i, nm in enumerate(names):
        a1.plot(t, vs[:, i], lw=1.2, label=f"{nm}  {verdicts[i]}")
        a2.plot(t, fl[:, i], lw=1.2)
    a1.set_ylabel("v.sum()  (total mass)")
    a1.legend(fontsize=8)
    a1.set_title(f"{label}: a glider conserves mass; a worm keeps gaining it")
    a2.axhline(FILL_CAP, color="k", ls="--", lw=0.8)
    a2.set_ylabel(f"fill (v>0.1);  dashed = {FILL_CAP} cap")
    a2.set_xlabel("step")
    fig.tight_layout()
    fig.savefig(png, dpi=110)
    print(f"wrote {png}")

    n = verdicts.count("GLIDER")
    print(f"\n{label}: {'PASS' if n else 'FAIL'} — {n} glider(s) of {len(names)}.")
    return verdicts


# ---------- stage 5: do the published u-skate coordinates transfer at all? ----------

# Stage 2 scanned k in 8 steps across 0.0605-0.0635, so dk = 4.3e-4. The reported
# u-skate band is about 1e-4 wide, which a 4.3e-4 stride can step straight over.
# Stage 5 rescans k nine times finer. It is a test of the "published (f,k) transfer
# directly" claim in HANDOFF.md, not only another glider hunt: if nothing with flat
# mass appears anywhere in this band, that claim is what is wrong.
S5_F = (0.0620, 0.0682)       # the reported u-skate f, and stage 4's chevron f
S5_K = (0.0600, 0.0640)
S5_DK = 5e-5                  # 81 k values, 9x finer than stage 2


def s5_pairs():
    ks = np.arange(S5_K[0], S5_K[1] + S5_DK / 2, S5_DK)
    return [(ff, float(kk)) for ff in S5_F for kk in ks], len(ks)


def report_stage5(v, names, vs, fl, px, py, unstable, sample, ncol, png, txt, npz):
    np.savez_compressed(npz, vs=vs, fl=fl, px=px, py=py, sample=sample,
                        names=np.array(names))
    print(f"wrote {npz}")
    grow, speed, fmax, verdicts = glider_verdicts(vs, fl, px, py, unstable, sample)
    pairs, nk = s5_pairs()
    kk = np.array([p[1] for p in pairs[:nk]])

    lines = ["f\tk\tv_sum_end\tgrow_2nd_half\tfill_max\tspeed_px_per_1k\tverdict"]
    for i, (pf, pk) in enumerate(pairs):
        lines.append(f"{pf:.4f}\t{pk:.5f}\t{vs[-1, i]:.1f}\t{grow[i]:+.4f}\t"
                     f"{fmax[i]:.3f}\t{speed[i]:.3f}\t{verdicts[i]}")
    open(txt, "w").write("\n".join(lines) + "\n")
    print(f"wrote {txt}")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    for j, ff in enumerate(S5_F):
        sl = slice(j * nk, (j + 1) * nk)
        a1.plot(kk, grow[sl], lw=1.2, marker=".", ms=3, label=f"f={ff:.4f}")
        a2.plot(kk, speed[sl], lw=1.2, marker=".", ms=3, label=f"f={ff:.4f}")
    a1.axhline(GROW_TOL, color="k", ls="--", lw=0.8)
    a1.axvline(0.0609, color="r", ls=":", lw=1.0)   # the reported u-skate k
    a1.set_yscale("symlog", linthresh=1e-3)
    a1.set_ylabel("mass growth, 2nd half")
    a1.set_title(f"Stage 5: k rescanned at dk={S5_DK:g}. Dashed = the {GROW_TOL} flat-mass "
                 f"cut; dotted red = reported u-skate k=0.0609")
    a1.legend(fontsize=9)
    a2.axvline(0.0609, color="r", ls=":", lw=1.0)
    a2.set_ylabel("speed, px per 1000 steps")
    a2.set_xlabel("k")
    fig.tight_layout()
    fig.savefig(png, dpi=110)
    print(f"wrote {png}")

    order = np.argsort(grow)
    print("\nten flattest tiles (a glider must appear near the top):")
    for i in order[:10]:
        print(f"  f={pairs[i][0]:.4f} k={pairs[i][1]:.5f}  grow={grow[i]:+.4f}  "
              f"fill={fmax[i]:.3f}  speed={speed[i]:.3f}  {verdicts[i]}")
    n = verdicts.count("GLIDER")
    print(f"\nstage 5: {'PASS' if n else 'FAIL'} — {n} glider(s) of {len(names)}.")
    if not n:
        print("  No flat-mass moving structure anywhere in the rescanned band.")
        print("  This rules out k resolution as the explanation. It does NOT show that")
        print("  the published (f,k) fail to transfer: only the asym seed was run, so")
        print("  seed inadequacy remains an equally live explanation. Do not conflate.")
    for vd in ("soliton", "worm-growing", "decaying", "worm-filled", "dead", "unstable"):
        print(f"  {vd:12s} {verdicts.count(vd)}")


# ---------- E1: replicate Ready's Munafo_glider.vti exactly ----------

# Every number here is read off Patterns/GrayScott1984/U-Skate/Munafo_glider.vti in
# github.com/GollyGang/ready. Three things that file leaves implicit, checked in its
# source rather than assumed:
#   * the boundary. The <rule> carries no wrap attribute and AbstractRD.cpp:215
#     defaults wrap to true, so mode="wrap" is right.
#   * the Laplacian. Ready's default 2-D stencil (stencils.cpp:499) is the Mehrstellen
#     [[1,4,1],[4,-20,4],[1,4,1]]/6, and KERN above is exactly 0.3x it. So a Ready D
#     divides by K_SCALE to become a D for this repo: 0.164 -> 0.5467, and this repo's
#     own Du=1.0 reads back as Ready's 0.30.
#   * the rectangles. overlays.cpp:631 tests index/N inclusive on both ends, with the
#     index counted from 0 and N the full dimension. e1_seed reproduces that literally.
# Ready does not clip u and v, so E1 runs with clip=False.
K_SCALE = 0.3
E1 = dict(H=64, W=128, Du=0.164, Dv=0.082, f=0.062, k=0.06093, u_bg=0.5, v_bg=0.3)
E1_RECTS = [(0.40, 0.62, 0.56, 0.74),   # x0, y0, x1, y1, as fractions of W and H
            (0.40, 0.40, 0.56, 0.52),
            (0.48, 0.50, 0.56, 0.62)]
E1_DEV = 0.05      # a cell counts as "structure" once |v - background| passes this


def e1_seed(H, W):
    """u=0.5 and v=0.3 everywhere, then v=0 in three rectangles. Only chemical b is
    overwritten, so u stays 0.5 inside the rectangles too."""
    u = np.full((H, W), E1["u_bg"])
    v = np.full((H, W), E1["v_bg"])
    rx, ry = np.arange(W) / W, np.arange(H) / H
    for x0, y0, x1, y1 in E1_RECTS:
        v[np.ix_((ry >= y0) & (ry <= y1), (rx >= x0) & (rx <= x1))] = 0.0
    return u, v


def run_e1(Du=E1["Du"], steps=50000, sample=50, nsnap=8, dtype=np.float32, hw=None,
           video=None, vstride=100):
    """One tile, Du given in Ready's units. Dv tracks it at the file's ratio of 0.5,
    which is also this repo's, so E2 can walk one knob from 0.164 to 0.30.

    hw overrides the 64x128 grid. Gray-Scott is scale-invariant: scaling both D by
    lambda is exactly a spatial stretch by sqrt(lambda), so raising Du at a fixed
    grid shrinks the domain AND the seed relative to the glider's natural size.
    E1_RECTS are fractions, so passing hw scaled by sqrt(lambda) undoes both and
    separates a real lattice ceiling from that artifact.

    The live v=0.3 background breaks stage 2's metrics: v.sum() is almost all
    background and (v>0.1).mean() is 1.0 at step 0, so glider_verdicts would call a
    perfect glider "worm-filled". Everything below is measured on the deviation from
    the background, |v - median(v)|, which reduces to plain v when the background is
    dead — the stage 2 case. glider_verdicts itself is unchanged.
    """
    H, W = hw or (E1["H"], E1["W"])
    u0, v0 = e1_seed(H, W)
    u, v = u0[None].astype(dtype), v0[None].astype(dtype)
    f = np.full((1, 1, 1), E1["f"], dtype)
    k = np.full((1, 1, 1), E1["k"], dtype)
    kern3 = KERN.astype(dtype)[None]
    buf = make_buffers(u.shape, dtype)
    du, dv = Du / K_SCALE, Du / 2 / K_SCALE       # Ready units -> this repo's

    thx = 2 * np.pi * np.arange(W) / W
    thy = 2 * np.pi * np.arange(H) / H
    cx, sx, cy, sy = np.cos(thx), np.sin(thx), np.cos(thy), np.sin(thy)
    nsamp = steps // sample
    vs, fl = np.empty((nsamp, 1)), np.empty((nsamp, 1))
    ax, ay, bg = np.empty((nsamp, 1)), np.empty((nsamp, 1)), np.empty(nsamp)
    snaps, snap_at = [], set(np.linspace(0, steps - 1, nsnap).astype(int).tolist())
    unstable = np.zeros(1, bool)
    peak = 0.0

    print(f"E1: 1 tile {W}x{H}, Ready Du={Du:g} Dv={Du/2:g} -> repo Du={du:.4f} "
          f"Dv={dv:.4f}, f={E1['f']} k={E1['k']}, {steps} steps, unclipped, "
          f"{np.dtype(dtype).name}", flush=True)

    # Frames stream straight into ffmpeg, one at a time, as demo.py:203 does -- the run
    # never holds more than the current frame. nearest-neighbour upscaling, not lanczos:
    # at 128x64 a smooth filter blurs the glider into a smudge, and x8 keeps any grid
    # even for yuv420p. The ramp below is render_grid's, so video and filmstrip match.
    enc = None
    if video:
        enc = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo",
             "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", "30", "-i", "-",
             "-vf", "scale=iw*8:ih*8:flags=neighbor",
             "-c:v", "libx264", "-crf", "18", "-preset", "medium",
             "-pix_fmt", "yuv420p", video], stdin=subprocess.PIPE)
        print(f"  video: every {vstride} steps -> {steps//vstride} frames, "
              f"{steps/vstride/30:.0f}s at 30fps, {W*8}x{H*8}", flush=True)

    t0 = time.perf_counter()
    for s in range(steps):
        m = step_batch(u, v, f, k, du, dv, kern3, buf, check=True, clip=False)
        unstable |= ~(m <= 5.0)
        peak = max(peak, float(m[0]))
        if s in snap_at:
            snaps.append(v[0].copy())
        if enc is not None and s % vstride == 0:
            t = np.clip((v[0] - 0.05) / 0.30, 0.0, 1.0)
            t = t * t * (3 - 2 * t)
            enc.stdin.write(np.dstack([(t * 255).astype(np.uint8)] * 3).tobytes())
        if s % sample == 0:
            j = s // sample
            b = np.median(v, axis=(1, 2), keepdims=True)
            dev = np.abs(v - b)
            bg[j] = b[0, 0, 0]
            vs[j] = dev.sum(axis=(1, 2), dtype=np.float64)
            fl[j] = (dev > E1_DEV).mean(axis=(1, 2), dtype=np.float64)
            ax[j] = _ang(dev.sum(axis=1, dtype=np.float64), cx, sx)
            ay[j] = _ang(dev.sum(axis=2, dtype=np.float64), cy, sy)
        if s % 10000 == 0 and s:
            el = time.perf_counter() - t0
            print(f"  step {s}/{steps}  {el/s*1000:.2f} ms/step  "
                  f"eta {(steps-s)*el/s/60:.1f} min", flush=True)
    print(f"  done in {(time.perf_counter()-t0)/60:.1f} min", flush=True)
    if enc is not None:
        enc.stdin.close()
        assert enc.wait() == 0, "video encode failed"   # the check for the whole path
        print(f"  wrote {video} ({os.path.getsize(video)/1e6:.1f} MB)")
    print(f"  pre-clip peak max(u,v) = {peak:.4f}  "
          f"(demo.py's [0,1] clip would {'HAVE FIRED' if peak > 1.0 else 'not have fired'})")
    print(f"  background median v: {bg[0]:.5f} -> {bg[-1]:.5f}")

    px = np.unwrap(ax, axis=0) * W / (2 * np.pi)
    py = np.unwrap(ay, axis=0) * H / (2 * np.pi)
    names = [f"E1 Du{Du:.4f}"]
    return v, names, vs, fl, px, py, unstable, sample, np.stack(snaps), snap_at


# ---------- E2: how far can Du be pushed before the glider dies? ----------

# E1 otherwise fixed. 0.164 is Ready's value; 0.30 is what this repo's Du=1.0 becomes
# once the 0.3x stencil factor is taken out.
#
# WARNING: this walk holds the grid at 128x64, and that makes its answer an artifact. Gray-
# Scott is scale-invariant: scaling both D by lambda is exactly a spatial stretch by
# sqrt(lambda), so raising Du here shrinks the domain AND the seed relative to the
# glider's natural size. The death it reports at Du=0.2735 is the seed leaving the
# skater's basin, not a lattice ceiling. Run `--e1 --du X --scaled` for the real
# number: it stretches the grid by sqrt(X/0.164) and the fractional E1_RECTS follow.
# Measured that way the ceiling is Du_ready 0.340-0.350 (repo 1.133-1.167), so this
# repo's own Du=1.0 does support a glider. Stages 2, 4 and 5 were NOT searching a
# region where the structure cannot exist; their initial condition was the blocker.
E2_DU = np.round(np.arange(0.164, 0.3001, 0.01), 5).tolist() + [0.30]


def run_e2(steps=60000, path=None):
    rows = []
    for i, d in enumerate(E2_DU):
        print(f"\n--- E2 {i+1}/{len(E2_DU)} ---", flush=True)
        v, names, vs, fl, px, py, unstable, sample, _, _ = run_e1(Du=d, steps=steps)
        grow, speed, fmax, verdicts = glider_verdicts(vs, fl, px, py, unstable, sample)
        rows.append((d, vs[-1, 0], grow[0], fmax[0], speed[0], verdicts[0]))
        print(f"  Du={d:.3f} (repo {d/K_SCALE:.4f}) -> {verdicts[0]}", flush=True)

    lines = ["Du_ready\tDu_repo\tdev_sum_end\tgrow_2nd_half\tfill_max\tspeed_px_per_1k\tverdict"]
    for d, s, g, fm, sp, vd in rows:
        lines.append(f"{d:.3f}\t{d/K_SCALE:.4f}\t{s:.1f}\t{g:+.4f}\t{fm:.3f}\t{sp:.3f}\t{vd}")
    if path:
        open(path, "w").write("\n".join(lines) + "\n")
        print(f"\nwrote {path}")
    print("\n".join(lines))
    live = [d for d, _, _, _, _, vd in rows if vd == "GLIDER"]
    print(f"\nE2: at a FIXED 128x64 grid the glider survives at Du_ready in "
          f"{min(live):.3f}..{max(live):.3f} (repo {min(live)/K_SCALE:.4f}.."
          f"{max(live)/K_SCALE:.4f}) of {len(E2_DU)} tested. This is NOT the ceiling: "
          f"the grid must stretch by sqrt(Du/0.164) or the seed shrinks with Du. "
          f"Rerun `--e1 --du X --scaled`, which gives 0.340..0.350."
          if live else "\nE2: no glider at any Du tested.")


# ---------- the load-bearing check ----------

def selftest():
    import demo
    cfg = demo.CONFIGS["a"]
    u0, v0 = demo.init_grid(cfg, np.random.default_rng(cfg["seed"]))
    f, k = cfg["feed"], cfg["kill"]

    ru, rv = u0.copy(), v0.copy()
    for _ in range(200):
        demo.step(ru, rv, f, k)

    u, v = u0[None].copy(), v0[None].copy()       # float64, one tile
    buf = make_buffers(u.shape, u.dtype)
    fa = np.full((1, 1, 1), f)
    ka = np.full((1, 1, 1), k)
    kern3 = KERN[None]
    for _ in range(200):
        step_batch(u, v, fa, ka, 1.0, 0.5, kern3, buf)
    du, dvv = np.abs(u[0] - ru).max(), np.abs(v[0] - rv).max()
    print(f"batched vs demo.step, 200 steps, coral, float64: "
          f"max|du|={du:.3e} max|dv|={dvv:.3e}")
    assert du < 1e-9 and dvv < 1e-9, "batched stepper disagrees with demo.step"

    u, v = init_state(3, 64, np.float32)          # float32 path runs and stays finite
    m = None
    for _ in range(50):
        m = step_batch(u, v, np.full((3, 1, 1), 0.0545, np.float32),
                       np.full((3, 1, 1), 0.062, np.float32), 1.0, 0.5,
                       KERN.astype(np.float32)[None],
                       make_buffers(u.shape, np.float32), check=True)
    assert np.isfinite(m).all() and (m <= 5.0).all(), "float32 path diverged"
    assert v.std() > 1e-6, "float32 path flatlined"

    sm = 10                                       # tail_metrics on synthetic tracks
    tt = np.arange(400)
    tvs = np.stack([np.full(400, 100.0), 100 + 0.5 * tt], 1)      # flat mass, rising mass
    tpx = np.stack([0.03 * tt, np.zeros(400)], 1)                 # 6 px/2000, still
    tpy = np.zeros((400, 2))
    d, fl = tail_metrics(tvs, tpx, tpy, sm)
    exp = 0.03 * (399 - 200)   # the window is [-200:], so 199 gaps, not 200. As shipped.
    assert abs(d[0] - exp) < 1e-9 and d[1] == 0.0, f"tail displacement wrong: {d}"
    assert fl[0] and not fl[1], f"flat-mass test wrong: {fl}"
    print(f"tail_metrics on synthetic tracks: disp={d.round(3).tolist()} flat={fl.tolist()}")

    S = 64                                        # torus centroid survives a wrap
    b = _disc(S, 32, 2, 5).astype(np.float64)[None]
    th = 2 * np.pi * np.arange(S) / S
    a = np.array([_ang(np.roll(b, int(sh), axis=2).sum(axis=1), np.cos(th), np.sin(th))
                  for sh in range(0, -20, -2)])
    px = np.unwrap(a, axis=0) * S / (2 * np.pi)
    err = np.abs(np.diff(px, axis=0) - (-2.0)).max()
    print(f"torus centroid across the wrap edge: max step error {err:.2e} px")
    assert err < 1e-6, "centroid does not track a blob across the wrap edge"

    # E1 rests on two claims about Ready. Both are checkable here, not by code reading.
    mehr = np.array([[1., 4., 1.], [4., -20., 4.], [1., 4., 1.]]) / 6.0  # stencils.cpp:499
    assert np.abs(KERN - K_SCALE * mehr).max() < 1e-15, "KERN is not 0.3x Ready's stencil"
    print(f"KERN vs {K_SCALE}x Ready's Mehrstellen stencil: exact")

    eu, ev = e1_seed(E1["H"], E1["W"])             # overlays.cpp:631 rasterisation
    hole = ev == 0.0
    ys, xs = np.nonzero(hole)
    assert (eu == 0.5).all(), "u must be 0.5 everywhere, rectangles included"
    assert int(hole.sum()) == 380, f"seed has {int(hole.sum())} zeroed cells, want 380"
    assert (xs.min(), xs.max()) == (52, 71), f"seed x span {xs.min()}-{xs.max()}, want 52-71"
    assert (ys.min(), ys.max()) == (26, 47), f"seed y span {ys.min()}-{ys.max()}, want 26-47"
    assert not hole[:, 52:62][(np.arange(64) >= 34) & (np.arange(64) <= 39)].any(), \
        "the third rectangle must reach only x>=62"
    print(f"e1_seed: {int(hole.sum())} zeroed cells, x {xs.min()}-{xs.max()}, "
          f"y {ys.min()}-{ys.max()}, u flat at 0.5")
    print("selftest OK")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage1", action="store_true")
    ap.add_argument("--stage2", action="store_true")
    ap.add_argument("--stage4", action="store_true",
                    help="re-run stage 2's four near-misses alone, 40000 steps")
    ap.add_argument("--stage5", action="store_true",
                    help="rescan k 9x finer at two f values, 160 px, 20000 steps")
    ap.add_argument("--e1", action="store_true",
                    help="replicate Ready's Munafo_glider.vti: 1 tile, 128x64, unclipped")
    ap.add_argument("--du", type=float, default=E1["Du"],
                    help="E1 only: Du in Ready's units. 0.164 = the file, 0.30 = this repo")
    ap.add_argument("--f64", action="store_true", help="E1 only: run in float64")
    ap.add_argument("--e2", action="store_true",
                    help="walk E1's Du from Ready's 0.164 to this repo's 0.30")
    ap.add_argument("--scaled", action="store_true",
                    help="E1 only: stretch the grid by sqrt(du/0.164), the scaling "
                         "symmetry, so the seed keeps its size relative to the glider")
    ap.add_argument("--video", action="store_true",
                    help="E1 only: also write an MP4, one frame every --vstride steps")
    ap.add_argument("--vstride", type=int, default=100,
                    help="E1 only: steps per video frame (default 100 = 33s per 100k)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--size", type=int, default=192)
    ap.add_argument("--steps", type=int, default=0,
                    help="0 = 8000 stage 1, 10000 stage 2, 40000 stage 4")
    ap.add_argument("--ratio", type=float, default=0.5, help="D_v/D_u, must be <1")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        sys.exit(0)
    if not 0 < args.ratio < 1:
        ap.error("--ratio must lie in (0,1): v must diffuse slower than u")
    tag = f"_r{round(args.ratio * 100):03d}"
    if args.e2:
        run_e2(steps=args.steps or 60000,
               path=os.path.join(HERE, "sweep_e2_du_walk.txt"))
    elif args.e1:
        sc = (args.du / E1["Du"]) ** 0.5 if args.scaled else 1.0
        p = os.path.join(HERE, f"sweep_e1_du{round(args.du*1000):03d}"
                               + ("_scaled" if args.scaled else "")
                               + ("_f64" if args.f64 else ""))
        out = run_e1(Du=args.du, steps=args.steps or 50000, hw=(
                     round(E1["H"] * sc), round(E1["W"] * sc)),
                     dtype=np.float64 if args.f64 else np.float32,
                     video=p + ".mp4" if args.video else None, vstride=args.vstride)
        np.save(p + "_v.npy", out[0])
        snaps, snap_at = out[8], sorted(out[9])
        report_stage4(*out[:8], 2, p + ".png", p + ".txt", p + "_tracks.npz", label="E1")
        render_grid(snaps, [(f"step {s}", (230, 225, 210)) for s in snap_at],
                    [None] * len(snaps), 2, p + "_film.png")
    elif args.stage5:
        out = run_stage2(size=args.size if args.size != 192 else 160,
                         steps=args.steps or 20000, Dv=args.ratio,
                         pairs=s5_pairs()[0], keep_seeds={"asym"}, label="stage 5")
        p = os.path.join(HERE, f"sweep_uskate{tag}")
        np.save(p + "_v.npy", out[0])
        report_stage5(*out, p + ".png", p + ".txt", p + "_tracks.npz")
    elif args.stage4:
        out = run_stage2(size=args.size, steps=args.steps or 40000, Dv=args.ratio,
                         pairs=NEAR_MISS, keep_seeds={"asym"})
        p = os.path.join(HERE, f"sweep_glider{tag}")
        np.save(p + "_v.npy", out[0])
        report_stage4(*out, p + ".png", p + ".txt", p + "_tracks.npz")
    elif args.stage2:
        out = run_stage2(size=args.size, steps=args.steps or 10000, Dv=args.ratio)
        np.save(os.path.join(HERE, f"sweep_seeds{tag}_v.npy"), out[0])
        report_stage2(*out, os.path.join(HERE, f"sweep_seeds{tag}.png"),
                      os.path.join(HERE, f"sweep_seeds{tag}.txt"))
    elif args.stage1:
        out = run_stage1(size=args.size, steps=args.steps or 8000, Dv=args.ratio)
        np.save(os.path.join(HERE, f"sweep_fk{tag}_v.npy"), out[0])  # re-render is 20 min
        labels, bars = sheet_labels(out[1], out[2], out[3], out[4], out[6])
        render_grid(out[0], labels, bars, N, os.path.join(HERE, f"sweep_fk{tag}.png"))
        write_table(*out[1:], os.path.join(HERE, f"sweep_fk{tag}.txt"))
    else:
        ap.error("pick --stage1, --stage2 or --selftest")
