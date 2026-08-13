# HANDOFF — resume point for reaction-diffusion-simulation

**Read this first each new session, then `PLAN.html` for the full spec.**
This file is the live "what to do next"; `PLAN.html` is the standing plan.
There is no repo-level `CLAUDE.md` — standing conventions come from the global
`~/.claude/CLAUDE.md`.

## Current state (as of latest push)

- **Shipped, commit `1eef904`:** `demo.py` — two Gray-Scott reaction-diffusion
  demos with generated audio. Config `a` = coral (`f=0.0545, k=0.062`), config
  `b` = mitosis (`f=0.0367, k=0.0649`). Outputs `coral.mp4`, `mitosis.mp4`, plus
  spectrograms.
- **Shipped, commit `6c05098`:** `README.md` rewritten as Markdown; GIF previews
  added. `documentation.html` (5 MB, embedded media) is the long-form write-up.
- **New this session:** `PLAN.html` — a full dev plan for sweeping the pattern
  space to find stripes, spots, worms, waves and gliders. Includes measured
  benchmarks and a cost section. **No code was written for it.**
- `demo.py` is **unmodified** and must stay that way (see Next task).
- Everything committed and pushed to `main`
  (https://github.com/az9713/reaction-diffusion-simulation.git). Working tree
  clean.

## Next task

**Write `sweep.py`, stage 1 only.** `PLAN.html` is the complete spec — read the
"Stage 1", "Files and interface", and "Order of work" sections. Summary:

- Produce one contact-sheet PNG: 12 × 12 tiles, `f` from 0.010 to 0.090, `k`
  from 0.045 to 0.070, at fixed `D_u=1.0`, `D_v=0.5`, `dt=1`.
- **Do not modify `demo.py`.** `sweep.py` carries its own batched float32
  stepper built on `scipy.ndimage.convolve(Z, K, mode="wrap")`. Import
  `demo.laplacian` / `demo.step` only as the reference the selftest checks
  against.
- **Acceptance check — do this first, stop if it fails.** One tile of the
  batched stepper must match `demo.step` at the coral parameters over 200 steps,
  to floating-point tolerance. Then the sheet passes only if the tile at
  `f=0.0545, k=0.062` shows a branching maze and the tile at `f=0.0367,
  k=0.0649` shows dividing spots. A wrong calibration tile means a broken
  harness, not interesting physics.
- Label each tile static or dynamic with mean `|Δv|` over the final 50 steps.
- Expect ~20 minutes of unattended compute per run at 192 px.

Stages 2 (designed seeds, glider detection) and 3 (diffusion-ratio sheets) come
after stage 1 has been read. Do not start them early.

If the user asks for something else, that takes precedence.

## Where to read things (reference, don't re-derive)

- `PLAN.html` — the spec and source of truth for the sweep. Covers the
  three-parameter rulebook `(f, k, D_v/D_u)`, why seeding is not a fourth axis,
  per-stage acceptance checks, measured benchmarks, and costs.
- `demo.py:37-42` — the 9-point Laplacian. `demo.py:63-68` — the reaction step
  and the `[0,1]` clip. `demo.py:90-92` — the existing `v.sum()` and x-centroid
  tracking, which the glider detector reuses.
- `README.md` — project overview. `documentation.html` — the long-form write-up
  whose claim about spontaneous symmetry breaking started this work.

## Facts already established — do not re-derive

- The 9-point Laplacian's most negative eigenvalue is **−1.6**, so explicit
  Euler is stable for `D·dt < 1.25`. `D_u = 1.0` sits near that ceiling.
- `scipy.ndimage.convolve(Z, K, mode="wrap")` with
  `K = [[.05,.2,.05],[.2,-1,.2],[.05,.2,.05]]` matches `demo.laplacian` to
  **2.2e-16**, and is **5× faster** than the eight `np.roll` calls.
- Measured on this machine, 144 tiles at 192 px, float32: **149 ms/step**
  (scipy) vs 774 ms/step (`np.roll`). 8000 steps = 20 min vs 103 min.
- This repo uses Karl Sims' exact Gray-Scott parameterization, so published
  `(f, k)` coordinates transfer directly; features are 2.5× larger than in the
  common `D_u=0.16` codes.
- Reported u-skate coordinates `f ≈ 0.062, k ≈ 0.0609` are **unverified here**.

## Session-transient scratch (regenerate; durable record is `PLAN.html`)

All benchmarks were run as throwaway `python -c "..."` one-liners in the repo
root — nothing was written to disk. To reproduce: import `demo.laplacian`,
build `(T, S, S)` float32 arrays, time 10–20 steps of each stepper variant with
`time.perf_counter()`, and compare against `scipy.ndimage.convolve`. The durable
record is the benchmark table in `PLAN.html`; re-run only if the machine or the
numpy/scipy version changes.

Watch for the Python closure trap that cost three attempts: an augmented
assignment (`u += L`, `TMP *= f`) inside a function makes that name local. Use
`np.add(a, b, out=a)` for module-level buffers.

## How to work (essentials)

- Ponytail full is the default: smallest change that works, stdlib and installed
  deps first, delete over add. `scipy` is already installed — do not add a
  dependency.
- Non-trivial logic leaves one runnable check behind. `demo.py` already has
  `--selftest`; `sweep.py` should have one too.
- Commit when the user says so. Do not commit speculatively.
