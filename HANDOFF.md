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
- **New this session:** `sweep.py` gained `--stage4` (the glider chase) and
  `--stage5` (the fine `k` rescan). `run_stage2` now returns the **full `vs`,
  `fl`, `px`, `py` tracks** plus `sample` and `ncol`, not just their last row;
  `report_stage2` derives the verdict itself through the new `tail_metrics`.
  `run_stage2` also takes optional `pairs=`, `keep_seeds=` and `label=`, so a few
  tiles can run longer without paying for the rest.
  Regression-checked: stage 2 at 64 px, 2000 steps gives a **byte-identical**
  `.txt` and `.png` before and after the refactor. `--selftest` has three
  checks, all passing (the new one drives `tail_metrics` with synthetic tracks).
  `.gitignore` gained `sweep_glider*` and `sweep_uskate*`.
- **Stage 4 answers the glider question: no. 0 of 4.** See "Facts already
  established".
- `documentation.html` gained three sections: stage 4's result, the two competing
  explanations for the missing glider, and what stage 5 tests. It embeds the
  stage-4 mass/fill figure (1000×800 JPEG, 90 KB). Render-checked over HTTP: no
  mojibake, no horizontal overflow, tag counts balanced.
- **The glider test now gates on a spread, not an endpoint difference.**
  `glider_verdicts` is shared by stages 4 and 5. A 300-step trial exposed the old
  rule: a mass curve that rises then falls has near-zero endpoint change and
  scored as a conserved glider — 11 false positives. Flatness is now
  `(max−min)/mean` over the second half, which is never smaller than the endpoint
  measure. Replaying stage 4's saved `.npz` through the stricter rule returns all
  four verdicts unchanged.
- Everything else committed and pushed to `main`
  (https://github.com/az9713/reaction-diffusion-simulation.git). Working tree
  clean apart from untracked `.ignore/`, which is local scratch — leave it
  untracked.

## Next task

Stages 1–5 have all run and all are documented. Pick one; ask Simon if unsure.

**A. Stage 6 — the seeding experiment (the only live scientific question).**
Stage 5 eliminated resolution, so the remaining fork is *coordinates vs seed*, and
only a seed experiment separates them. The cheapest decisive design: hold `(f, k)`
at the reported u-skate point `f=0.062, k=0.0609` and at `f=0.0682, k=0.0632`, and
vary the **seed** instead — several asymmetries, several sizes, and a few
noise-soup fields. Reuse `run_stage2(pairs=..., keep_seeds=...)`; the seed list is
built by `seed_shapes()`, so this is new shapes plus a call, not new machinery.
**Budget from a measured step rate at the actual array shape**, not by scaling —
that is the mistake stage 5 made. Note a soup field defeats centroid tracking, so
either keep single-structure seeds or add blob detection first.

**B. Stop.** Five stages ran, three null results are recorded honestly, and the
open question is named rather than papered over. This is a legitimate choice.

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
- **Stage 4 is a null result: 0 gliders of 4.** The four stage-2 near-misses,
  `asym` seed only, 192 px, 40 000 steps, 1.6 min. Selection rule: `asym`,
  verdict `unsettled`, `disp > 5` px, `fill < 0.35` — that is exactly
  `(0.060909, 0.063182)`, `(0.062, 0.06307143)`, `(0.068182, 0.063182)`,
  `(0.062, 0.0635)`. **Every one gains mass monotonically for the whole 40 000
  steps.** Growth over the second half: +47%, +56%, +88%, +199%. Three saturate
  the torus (`fill_max` 0.47–0.58); the fourth,
  `asym f=0.0682 k=0.0632` — the handoff's best candidate, the clean chevron —
  is still growing linearly at step 40 000 at only `fill=0.173`, so it is a slow
  worm, not a glider. The 6–10 px of stage-2 travel was a growing filament's
  centroid drifting, not a conserved structure moving. **The bistable window at
  `D_v/D_u = 0.5` in this parameterisation contains no glider.**
- The plateau in the two fastest curves is **domain saturation, not mass
  conservation** — that is what the `fill_max > 0.35` cut exists to catch. Read
  the fill panel of `sweep_glider_r050.png` before believing a flat `v.sum()`.
- **Stage 5 is a null result: 0 gliders and 0 solitons of 162.** `k` from 0.0600
  to 0.0640 at `Δk = 5e-5`, at `f = 0.0620` and `f = 0.0682`, `asym` seed, 160 px,
  20 000 steps, **72.9 min** (estimated 35 — see the cost note below). Verdicts:
  111 worm-filled, 51 worm-growing, 0 soliton, 0 decaying, 0 dead, 0 unstable.
  The band holds two regimes and nothing between: below `k ≈ 0.0623` the seed
  fills the grid (at the reported `k = 0.0609`, fill is **0.976** at `f=0.0620`
  and **0.888** at `f=0.0682`); above it every tile stays under 0.35 fill but
  keeps growing, smallest second-half growth **+0.22** (`f=0.0682`) and **+0.80**
  (`f=0.0620`). The ten flattest mass curves in the run all have fill 0.775–1.000
  — saturation again, not conservation.
- **What stage 5 proves, stated exactly.** It **eliminates `k` resolution** as the
  explanation for the missing glider. It eliminates nothing else. **Do not write
  that the published coordinates fail to transfer** — stage 5 ran the `asym` seed
  only, so seed inadequacy is an equally live explanation. Stage 2 showed
  *symmetric* seeds cannot travel; that is not evidence `asym` is a shape a glider
  grows from. Separating the two needs a **seeding experiment, not a finer sweep**,
  and none has been run. An earlier draft of `documentation.html`, `README.md` and
  the script's own output all made this overclaim; all three are now corrected.
- **Cost prediction failed by 2.1×.** Stage 5 was budgeted at 35 min by scaling
  stage 2's 150 ms/step by tile count and pixel area. Actual ≈ 219 ms/step. The
  area-scaling that held from 192 px to 64 px did **not** hold at 160 px with 162
  tiles. Re-measure at the real shape before quoting a runtime.
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

**Figure pipeline for `documentation.html`** — also throwaway, run from `.ignore/`.
The pattern, if more figures are ever needed:

1. Crop or downscale from `sweep_fk_r050.png` with PIL. Tile geometry is
   `pad=3, S=192, label=17`, so tile `i` sits at
   `x = pad + (i % ncol)*(S+pad)`, `y = pad + (i // ncol)*(S+label+pad)`.
2. Save as JPEG (`quality=88–92`) — 4 figures came to 318 KB total. Full-size
   PNGs would have added ~5 MB.
3. Base64-encode, substitute into a `{{PLACEHOLDER}}` in the section HTML, and
   insert the section immediately before `<footer class="page">`, which occurs
   exactly once. Back up the file first; assert the anchor count is 1.
4. Check tag balance by counting `<tag` against `</tag>` on a copy with the
   base64 payloads stripped (`re.sub(r'(base64,)[A-Za-z0-9+/=]+', ...)`) — that
   also makes the 5 MB file readable at 29 KB.

The durable record is the committed `documentation.html`. To change a figure,
edit that file directly rather than rebuilding this pipeline.

**Rendering check.** `file://` URLs are refused by the browser tool. Serve the
repo with `python -m http.server 8765 --bind 127.0.0.1`, open
`http://127.0.0.1:8765/documentation.html?v=N` — the query string is needed,
Chrome serves the stale copy otherwise — then stop the server by its task id.

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
