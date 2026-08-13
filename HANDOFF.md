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
- **GitHub Actions added, commit `e57048e`** (merged PR #1, created by
  `/install-github-app`, not by hand): `.github/workflows/claude.yml` (PR
  assistant) and `.github/workflows/claude-code-review.yml`. Opening a PR now
  triggers an automated Claude review. Simon does not normally use PRs — this
  arrived with the app install.
- **New this session, uncommitted:** `sweep.py` — stage 1 of `PLAN.html`, complete
  and run. `--selftest` matches `demo.step` to 1.4e-15 over 200 steps.
  `--stage1` ran 146 tiles at 192 px for 8000 steps in **21.3 min** (146 ms/step,
  as predicted). Both calibration tiles pass. Outputs `sweep_fk.png`,
  `sweep_fk.txt`, `sweep_fk_v.npy` — all gitignored, all regenerable.
  Rendering uses PIL, not the ffmpeg path `PLAN.html` suggested: PIL is already
  installed, keeps exact pixels, and avoids the ffmpeg `drawtext` font-path bug
  on this machine.
- Everything else committed and pushed to `main`
  (https://github.com/az9713/reaction-diffusion-simulation.git). Working tree
  clean apart from untracked `.ignore/`, which is local scratch — leave it
  untracked.

## Next task

**Stage 2 of `PLAN.html` — designed seeds inside the bistable window.** Stage 1
is finished and read. Add `--stage2` to `sweep.py`. Reuse `step_batch`,
`make_buffers` and the pre-clip check; write a new seed builder and a glider
detector.

Stage 1 found a wide bistable window at high `f`. Use these `(f, k)` pairs —
each already holds a single localised structure that does not fill the domain:

| f | k | what stage 1 shows | mean \|Δv\| |
|---|---|---|---|
| 0.0609 | 0.0632 | one cross-shaped ring | 1.5e-05 |
| 0.0682 | 0.0632 | one annulus | 1.4e-06 |
| 0.0755 | 0.0609 | one rounded-square ring | 6.6e-06 |
| 0.0609 | 0.0655 | 4 isolated static spots | 1.8e-07 |
| 0.0682 | 0.0655 | 4 isolated static spots | 1.5e-07 |
| 0.0755 | 0.0632 | 4 isolated static spots | 1.9e-07 |

Add the reported u-skate pair `f=0.062, k=0.0609` as a candidate. Stage 1 does
not cover it: the nearest tile `f=0.0609, k=0.0609` fills the domain with spots,
so the bistable boundary runs between `k=0.0609` and `k=0.0632` there. Sample
`k` finely across that gap.

Acceptance: PASS if one `(f, k, seed)` gives flat `v.sum()` and a non-zero
centroid speed held for 2000 steps. Unwrap the centroid before measuring speed —
the grid wraps. A null result is a real result; report it.

Stage 3 (diffusion-ratio sheets) needs no new code beyond a `--ratio` flag —
`D_u` and `D_v` are already arguments of `run_stage1`. Run it only if a question
remains.

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
- Stage 1 measured: 146 tiles, 192 px, 8000 steps, float32 = **21.3 min**, 146
  ms/step. Of 146 tiles, **42 die** (high `f`, high `k`) and 104 live. No tile
  broke the pre-clip bound, so no run was hiding a divergence behind the clip.
- The `mean |Δv|` values fall in three bands, not two: **> 1e-4** genuinely
  dynamic (waves, replicating spots, worms — the low-`f` corner); **1e-7 to
  1e-5** static solitons; **0** filled or dead. Coral (3.5e-05) and mitosis
  (4.4e-05) sit between the bands — still creeping at step 8000. The `DYN =
  1e-4` cutoff in `sweep.py` is a rough two-way cut; read the number, not the
  colour.
- The demo MP4s run **longer** than the sheet: coral 25 200 steps, mitosis
  16 800. The sheet at 8000 steps shows an earlier moment of the same pattern.

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
