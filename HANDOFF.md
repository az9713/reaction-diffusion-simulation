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
- **Shipped, commit `df5675d`:** `sweep.py` — all three stages of `PLAN.html`,
  written and run. `--selftest` has two checks, both passing: the batched
  stepper against `demo.step` (1.4e-15 over 200 steps) and the torus centroid
  across the wrap edge (1.8e-15 px/step). Outputs are gitignored and
  regenerable: `sweep_fk_r{030,050,070}.{png,txt,_v.npy}` and
  `sweep_seeds_r050.*`.
  Rendering uses PIL, not the ffmpeg path `PLAN.html` suggested: PIL is already
  installed, keeps exact pixels, and avoids the ffmpeg `drawtext` font-path bug
  on this machine.
- **Stage 1 PASSES calibration**, stage 3 ran at ratios 0.3 and 0.7, **stage 2
  returns a null result** — see "Facts already established" below.
- The GitHub About box was set this session via `gh repo edit`. `README.md` and
  `documentation.html` both now cover the sweep (commits `719c440`, `0025b38`).
  `documentation.html` also gained the `<meta charset="utf-8">` it had always
  lacked — without it every em dash renders as mojibake over HTTP.
  `sweep_preview.jpg` is the only sweep image tracked in git.
- Everything else committed and pushed to `main`
  (https://github.com/az9713/reaction-diffusion-simulation.git). Working tree
  clean apart from untracked `.ignore/`, which is local scratch — leave it
  untracked.

## Next task

`PLAN.html` is fully executed. Pick one; ask Simon if unsure.

**A. Chase the near-miss glider (the open scientific question).** Stage 2 found
no glider, but four asymmetric-seed tiles moved 6–10 px in the final 2000 steps
while still growing, so they failed the flat-`v.sum()` test rather than the
motion test. The best is `asym, f=0.0682, k=0.0632`, which formed a clean
travelling chevron. To settle it, `run_stage2` must **return the `vs`, `px`, `py`
tracks**, not just their last row — right now the trend is thrown away and the
verdict cannot be re-judged without a 25-minute re-run. Then run those four
pairs alone for 40 000 steps and plot `v.sum()` against time. A structure whose
mass keeps rising is a growing worm, not a glider.

**B. Stop.** The plan is done and the results are recorded. This is a legitimate
choice.

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
- **Stage 3, three ratios.** `D_v/D_u` throttles the whole map. At 0.3: 142 of
  146 tiles live, 3 soliton-like, features fine. At 0.5: 104 live, 13
  soliton-like. At 0.7: 68 live, 6 soliton-like, features coarse, and **the
  coral and mitosis coordinates both die** — the Turing condition needs `D_v`
  well below `D_u`. No new pattern class at either ratio, as `PLAN.html`
  predicted. **Ratio 0.5 has the widest bistable window of the three**, so it is
  the right place to hunt gliders. Do not re-run stage 3.
- **Stage 2 is a null result: 0 gliders.** 154 tiles (14 `(f,k)` pairs × 11
  seeds), 192 px, 10 000 steps, 25.0 min. Verdicts: 28 soliton, 51 grew, 75
  unsettled, 0 dead, 0 unstable. Symmetric seeds (single, and all 8 blob pairs)
  never move — as expected, a symmetric seed has no direction to travel in.
  **Only the `asym` seed produces motion**, at `f≈0.061–0.068, k≈0.0631–0.0632`:
  6–10 px of centroid travel over the final 2000 steps, but `v.sum()` is still
  rising, so these are growing filaments, not conserved gliders. `asym,
  f=0.0682, k=0.0632` grew a clean chevron and is the best candidate.
- The reported u-skate pair `f=0.062, k=0.0609` produced **nothing localised**.
  Every seed there either grew to fill the domain or sat still. Across the fine
  `k` sweep 0.0605–0.0635 at `f=0.062`, no combination gave a moving soliton.
  Treat the published coordinates as **not reproduced in this parameterisation**.

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
