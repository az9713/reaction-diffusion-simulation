# Stage 1 of PLAN.html — the f-k contact sheet for the Gray-Scott solver in demo.py.
# demo.py is not modified; it is imported only as the reference the selftest checks.
# Usage: python sweep.py --selftest        # batched stepper vs demo.step, seconds
#        python sweep.py --stage1          # 12x12 sheet + 2 calibration tiles, ~20 min
import argparse, os, sys, time
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


def step_batch(u, v, f, k, Du, Dv, kern3, buf, check=False):
    """One Euler step on a (T,H,W) stack. Same term order as demo.step:63-68.

    f and k are (T,1,1) in the stack's dtype. Returns the per-tile pre-clip max
    when check=True, else None. kern3 is size 1 on the leading axis, so the wrap
    convolution cannot bleed between tiles.
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
    T, S, _ = v.shape
    t = np.clip((v - 0.05) / 0.30, 0.0, 1.0)
    t = t * t * (3 - 2 * t)                       # same ramp as demo.colorize
    gray = (t * 255).astype(np.uint8)
    pad, lab = 3, 17
    cw, ch = S + pad, S + lab + pad
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
            d.rectangle([x, y + S + lab - 1, x + max(int(S * frac), 1), y + S + lab],
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


def run_stage2(size=192, steps=10000, Du=1.0, Dv=0.5, dtype=np.float32, sample=10):
    pairs = BISTABLE + [(USKATE_F, kk) for kk in np.linspace(*USKATE_K, 8)]
    seeds = seed_shapes(size)
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
    unstable = np.zeros(T, bool)

    print(f"stage 2: {T} tiles ({len(pairs)} f-k pairs x {len(seeds)} seeds), "
          f"{size} px, {steps} steps", flush=True)
    t0 = time.perf_counter()
    for s in range(steps):
        m = step_batch(u, v, f, k, Du, Dv, kern3, buf, check=(s % 100 == 0))
        if m is not None:
            unstable |= ~(m <= 5.0)
        if s % sample == 0:
            j = s // sample
            vs[j] = v.sum(axis=(1, 2), dtype=np.float64)
            ax[j] = _ang(v.sum(axis=1, dtype=np.float64), cos_t, sin_t)
            ay[j] = _ang(v.sum(axis=2, dtype=np.float64), cos_t, sin_t)
        if s % 1000 == 0 and s:
            el = time.perf_counter() - t0
            print(f"  step {s}/{steps}  eta {(steps-s)*el/s/60:.1f} min", flush=True)
    print(f"  done in {(time.perf_counter()-t0)/60:.1f} min", flush=True)

    px = np.unwrap(ax, axis=0) * size / (2 * np.pi)   # unwrap: the grid wraps
    py = np.unwrap(ay, axis=0) * size / (2 * np.pi)
    n2 = 2000 // sample                                # the final 2000 steps
    disp = np.hypot(px[-1] - px[-n2], py[-1] - py[-n2])
    tail = vs[-n2:]
    flat = (tail.max(0) - tail.min(0)) / np.maximum(tail.mean(0), 1e-9) < 0.02
    fill = (v > 0.1).mean(axis=(1, 2), dtype=np.float64)
    return v, names, vs[-1], fill, disp, flat, unstable


def report_stage2(v, names, vsum, fill, disp, flat, unstable, path_png, path_txt):
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
    render_grid(v, labels, bars, len(seed_shapes(v.shape[1])), path_png)

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

    S = 64                                        # torus centroid survives a wrap
    b = _disc(S, 32, 2, 5).astype(np.float64)[None]
    th = 2 * np.pi * np.arange(S) / S
    a = np.array([_ang(np.roll(b, int(sh), axis=2).sum(axis=1), np.cos(th), np.sin(th))
                  for sh in range(0, -20, -2)])
    px = np.unwrap(a, axis=0) * S / (2 * np.pi)
    err = np.abs(np.diff(px, axis=0) - (-2.0)).max()
    print(f"torus centroid across the wrap edge: max step error {err:.2e} px")
    assert err < 1e-6, "centroid does not track a blob across the wrap edge"
    print("selftest OK")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage1", action="store_true")
    ap.add_argument("--stage2", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--size", type=int, default=192)
    ap.add_argument("--steps", type=int, default=0, help="0 = 8000 stage 1, 10000 stage 2")
    ap.add_argument("--ratio", type=float, default=0.5, help="D_v/D_u, must be <1")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        sys.exit(0)
    if not 0 < args.ratio < 1:
        ap.error("--ratio must lie in (0,1): v must diffuse slower than u")
    tag = f"_r{round(args.ratio * 100):03d}"
    if args.stage2:
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
