# HANDOFF — resume point for reaction-diffusion-simulation

**Read this first each new session, then `PLAN.html` for the full spec.**
This file is the live "what to do next"; `PLAN.html` is the standing plan.
There is no repo-level `CLAUDE.md` — standing conventions come from the global
`~/.claude/CLAUDE.md`.

Last updated 2026-08-13, after the literature audit. Previous state: commit
`91704cd` (contents rail in `documentation.html`).

## Current state (as of latest push)

- **`demo.py`, commit `1eef904`** — two Gray-Scott demos with generated audio.
  Config `a` = coral (`f=0.0545, k=0.062`), `b` = mitosis (`f=0.0367, k=0.0649`).
  Outputs `coral.mp4`, `mitosis.mp4`, spectrograms. **`demo.py` is unmodified by
  all sweep work and should stay that way** — `sweep.py` imports it only as the
  reference its selftest checks against.
- **`sweep.py`, commits `df5675d` → `6e9bafe` → `2c4005f`** — the whole parameter
  sweep. Five stages: `--stage1` (f-k sheet), `--stage2` (designed seeds),
  `--ratio` (stage 3), `--stage4` (near-miss chase), `--stage5` (fine `k` rescan).
  `--selftest` has three checks, all passing.
- **All five stages have run.** Stages 2, 4 and 5 are null results. See "Facts
  already established" — **do not re-run any of them.**
- **Docs are current and honest.** `README.md`, `documentation.html` (5.80 MB,
  embedded media) and `PLAN.html`'s status table all carry the stage 4 and 5
  results *and* the three corrections listed below. `documentation.html` also
  carries the 2026-08-13 literature audit — four sections, `#found`, `#gap`,
  `#missed`, `#bridge`, plus a contents rail. **`README.md` and `PLAN.html` do
  not yet mention the audit**; they are correct but incomplete.
- **GitHub Actions, commit `e57048e`** (from `/install-github-app`, merged PR #1):
  `.github/workflows/claude.yml` and `claude-code-review.yml`. Opening a PR
  triggers an automated review. Simon does not normally use PRs.
- Everything committed and pushed to `main`
  (https://github.com/az9713/reaction-diffusion-simulation.git). Working tree
  clean. `.ignore/` is local scratch and is now **gitignored** — an earlier
  `git add -A` swept all 20 of its files into the index; the ignore rule stops
  that recurring.
- Sweep outputs are gitignored and regenerable: `sweep_fk_r{030,050,070}.*`,
  `sweep_seeds_r050.*`, `sweep_glider_r050.*`, `sweep_uskate_r050.*`.
  `sweep_preview.jpg` is the only sweep image tracked in git.

## Next task

⚠️ **The seeding experiment previously written here was cancelled on 2026-08-13.**
It proposed holding `(f, k)` at `f=0.062, k=0.0609` and varying the seed. A
literature audit (see "The audit" below) found a complete working recipe, and
that plan was wrong in two ways: the diffusion constant is off by 1.83×, and
`f=0.0620` is a row where stage 2 produced **zero solitons in 88 tiles across all
eleven seeds**. Do not run it.

Do these in order. **E1 is cheap and has a binary outcome — start there.**

**E1 — replicate `Munafo_glider.vti` exactly.** One tile. `Du=0.164, Dv=0.082,
f=0.062, k=0.06093`, 128×64 periodic, background `u=0.5, v=0.3` **everywhere**,
then `v=0` in three rectangles (fractions of the grid): `(0.40,0.62)-(0.56,0.74)`,
`(0.40,0.40)-(0.56,0.52)`, `(0.48,0.50)-(0.56,0.62)`. Reuse
`run_stage2(pairs=..., keep_seeds=...)`; this is one new entry in `seed_shapes()`
plus a `Du`/`Dv` argument, not new machinery. Either a glider appears or the port
is wrong — both beat another sweep.

**E2 — walk `Du` from 0.164 up to 0.30** with E1 otherwise fixed, and find where
the glider dies. That measures whether this repo's `Du=1.0` could ever have
supported the structure. A number, not a fourth null.

**E3 — only then vary `(f, k)` and the seed.** Perturb outward from the working
point. Any new scan must use the live background, and should extend `k` past
`0.0640`: stage 2's strongest soliton band is at `k=0.0655`, outside every window
searched so far.

Three warnings, all learned the hard way:
1. **Budget from a measured step rate at the actual array shape.** Do not scale a
   benchmark by tile count and pixel area — that is how stage 5's estimate came
   out 2.1× low.
2. **A soup field defeats centroid tracking.** `_ang` follows one structure, not
   fifty. Keep single-structure seeds, or add blob detection first.
3. **`step_batch` clips `u` and `v` into [0,1]; Ready does not clip.** The clip
   has never been active in any run so far, but E1 starts from a different state.
   Keep the pre-clip check on.

If the user asks for something else, that takes precedence.

## Where to read things (reference, don't re-derive)

- `PLAN.html` — spec and source of truth for stages 1–3, plus a status table
  recording every outcome against its prediction. Stages 4 and 5 are *not* in it;
  they were added after it was written.
- `documentation.html` — the long-form write-up. Its "What stage 5 does not show"
  section is the honest statement of where the glider question stands.
- `demo.py:37-42` — the 9-point Laplacian. `demo.py:63-68` — the reaction step
  and the `[0,1]` clip.
- `sweep.py` — `glider_verdicts` is the shared glider test; `tail_metrics` is
  stage 2's; `s5_pairs` builds stage 5's grid.

## Facts already established — do not re-derive

### The audit — where the glider actually lives (2026-08-13, not yet run)

- **The recipe is public and complete.** Ready ships Munafo's glider as
  `Patterns/GrayScott1984/U-Skate/Munafo_glider.vti` in
  `github.com/GollyGang/ready` — 2.5 KB of XML, readable with `curl`. Values in
  E1 above. Backing paper: R. P. Munafo, *Stable localized moving patterns in the
  2-D Gray-Scott model*, arXiv:1501.01990.
- **Eight of fourteen knobs already matched.** Stage 5 matched the working file on
  the equation, the time step, the stencil family, `f`, `k`, the ratio, the
  boundary and the grid. Four differ; two (float32, and the `[0,1]` clip) are
  untested. The four are **`Du`** and **the initial condition** — and the
  initial condition is wrong three ways at once: dead background `(1, 0)` instead
  of live `(0.5, 0.3)`, `v` **raised** instead of **lowered**, and the wrong shape.
  Different basin of attraction; no `(f, k)` scan crosses between basins.
- **The kernels are commensurable.** Ready's default 2-D Laplacian
  (`src/readybase/stencils.cpp:499`) is the Mehrstellen 9-point
  `[[1,4,1],[4,-20,4],[1,4,1]]/6`. The Sims kernel at `demo.py:37-42` is **exactly
  0.3×** it. So this repo's `Du=1.0` reads as **0.30** against the file's
  **0.164** — 1.83× larger, and 80% of the explicit-Euler stability limit versus
  the file's 44%.
- **`k` was never the problem.** Munafo's Table 1 gives the stable band as
  `0.0608833 ≤ k ≤ 0.0609829` at `f=0.06`, and shows it moves by under `6e-6`
  across three grid refinements. Stage 5's `Δk = 5e-5` comb was correctly sized,
  and **2 of its 162 tiles sat inside that band** (`k=0.06090`, `0.06095` at
  `f=0.0620`). The run stood on the target for 72.9 minutes with the other two
  knobs wrong.
- **Stage 2's table already proved seed-dependence and was never read that way.**
  At `f=0.0682, k=0.0632`: `single` → soliton, `asym` → worm. Same coordinates,
  different attractor. Cross-tabulated 2026-08-13 from `sweep_seeds_r050.txt`,
  which has been on disk since 2026-08-12.
- Full write-up: `documentation.html`, sections `#found`, `#gap`, `#missed`,
  `#bridge`.

### The glider question, and the one claim not to repeat

- **Stage 2 is a null result: 0 gliders.** 154 tiles (14 `(f,k)` pairs × 11
  seeds), 192 px, 10 000 steps, 25.0 min. 28 soliton, 51 grew, 75 unsettled.
  Symmetric seeds (single, and all 8 blob pairs) **never move** — a symmetric seed
  has no direction to travel in. Only the `asym` seed produced motion.
- **Stage 4 is a null result: 0 gliders of 4.** The four stage-2 near-misses,
  `asym` only, 192 px, 40 000 steps, 1.6 min. Every one gains mass monotonically
  for the whole run: +47%, +56%, +88%, +199% across the second half. Three
  saturated the torus; the fourth (`f=0.0682, k=0.0632`, the clean chevron) is
  still growing linearly at step 40 000 at only `fill=0.173`. A slow worm.
- **Stage 5 is a null result: 0 gliders and 0 solitons of 162.** `k` 0.0600→0.0640
  at `Δk = 5e-5`, `f = 0.0620` and `0.0682`, `asym` seed, 160 px, 20 000 steps,
  **72.9 min**. 111 worm-filled, 51 worm-growing, 0 soliton. Two regimes, nothing
  between: below `k ≈ 0.0623` the seed fills the grid (at the reported `k=0.0609`,
  fill is **0.976** / **0.888**); above it tiles stay under 0.35 fill but never
  stop growing (smallest second-half growth **+0.22** / **+0.80**).
- ⚠️ **What stage 5 proves, stated exactly.** It **eliminates `k` resolution** as
  the explanation. It eliminates **nothing else**. **Do NOT write that the
  published u-skate coordinates fail to transfer into this parameterisation** —
  the audit above shows `f` and `k` transfer exactly, and `Du` plus the initial
  condition are what differ.
  Stage 5 ran the `asym` seed only, so seed inadequacy is an equally live
  explanation. Stage 2 showed *symmetric* seeds **cannot** travel — that is not
  evidence `asym` **can**. Separating the two needs a seeding experiment, not a
  finer sweep. Earlier drafts of `documentation.html`, `README.md` and the
  script's own output all made this overclaim; **all three were corrected in
  commit `2c4005f`** and a previous version of this handoff carried it too.
- The claim that this repo's Karl Sims parameterization makes published `(f, k)`
  coordinates **transfer directly** is the assumption under test, **not a
  settled fact**. It was recorded as settled for most of this project's life.
  Features here are 2.5× larger than in the common `D_u=0.16` codes.
- **A flat `v.sum()` is not evidence of a glider on its own.** Twice now the
  flattest mass curves in a run were structures that had filled the domain — the
  ten flattest in stage 5 all have `fill` between 0.775 and 1.000. That is what
  the `fill_max > 0.35` cut exists to catch. Always read the fill track.
- **Flatness is a spread, not an endpoint difference.** A mass curve that rises
  then falls has near-zero endpoint change. A 300-step trial scored 11 such
  curves as conserved gliders. `glider_verdicts` now gates on `(max−min)/mean`
  over the second half, which is never smaller than the endpoint measure.
  Replaying stage 4's saved `.npz` through it leaves all four verdicts unchanged.

### Numerics and performance

- The 9-point Laplacian's most negative eigenvalue is **−1.6**, so explicit Euler
  is stable for `D·dt < 1.25`. `D_u = 1.0` sits near that ceiling.
- `scipy.ndimage.convolve(Z, K, mode="wrap")` with
  `K = [[.05,.2,.05],[.2,-1,.2],[.05,.2,.05]]` matches `demo.laplacian` to
  **2.2e-16** and is **5× faster** than the eight `np.roll` calls. Measured: 144
  tiles at 192 px float32, **149 ms/step** vs 774 ms/step.
- ⚠️ **Do not scale a benchmark across array shapes.** Stage 5 was budgeted at 35
  min by scaling stage 2's 150 ms/step by tile count and pixel area; it ran at
  ~219 ms/step, **2.1× over**. Area-scaling held from 192 px to 64 px and failed
  at 160 px with 162 tiles. Measure at the real shape.
- Stage 1 measured: 146 tiles, 192 px, 8000 steps, float32 = **21.3 min**. 42
  tiles die (high `f`, high `k`), 104 live. No tile broke the pre-clip bound, so
  no run hid a divergence behind the clip.
- **Total compute across all five stages: 162.5 min.**

### The map

- The `mean |Δv|` values fall in **three** bands, not two: **> 1e-4** genuinely
  dynamic (the low-`f` corner); **1e-7 to 1e-5** static solitons; **0** filled or
  dead. Coral (3.5e-05) and mitosis (4.4e-05) sit between bands — still creeping
  at step 8000. `DYN = 1e-4` is a rough two-way cut; read the number, not the
  colour.
- **Stage 3, three ratios.** `D_v/D_u` throttles the whole map. At 0.3: 142 of 146
  live, 3 soliton-like. At 0.5: 104 live, 13 soliton-like. At 0.7: 68 live, 6
  soliton-like, and **coral and mitosis both die** — the Turing condition needs
  `D_v` well below `D_u`. No new pattern class at any ratio, as `PLAN.html`
  predicted. **Ratio 0.5 has the widest bistable window**, so it is where gliders
  were hunted. Do not re-run stage 3.
- The demo MP4s run **longer** than the sheet: coral 25 200 steps, mitosis 16 800.
  The sheet at 8000 steps shows an earlier moment of the same pattern.

## Session-transient scratch (regenerate; durable record is the committed file)

Benchmarks were throwaway `python -c "..."` one-liners; nothing on disk. The
durable record is the table in `PLAN.html`. Re-run only if the machine or the
numpy/scipy version changes.

**Figure/section pipeline for `documentation.html`** — throwaway, run from the
scratchpad. The pattern, if more sections are ever needed:

1. Write the section HTML to a scratch file with a `{{PLACEHOLDER}}` per figure.
2. Downscale the PNG with `PIL.Image.thumbnail((1000,1000))`, save JPEG
   `quality=90, optimize=True` (~90 KB each), base64-encode, substitute.
3. Insert before `<footer class="page">`. **Match the anchor with a
   whitespace-tolerant regex** — `re.compile(r'</section>\s*<footer class="page">')`
   — and assert exactly one match. A literal `'</section>\n\n<footer…'` broke on
   the second insert, because the first had left three newlines.
4. **Write with `open(path, "w", encoding="utf-8", newline="")`.** Plain
   `Path.write_text` translates `\n` to `\r\n` on Windows and churns the file.
5. Check tag balance by counting `<tag` against `</tag>` on a copy with base64
   payloads stripped (`re.sub(r'(base64,)[A-Za-z0-9+/=]+', ...)`) — that also
   makes the 5.8 MB file readable at ~47 KB.

To change a figure, edit the committed `documentation.html` directly rather than
rebuilding this pipeline.

**Rendering check.** `file://` URLs are refused by the browser tool. Serve with
`python -m http.server 8767 --bind 127.0.0.1` **from the repo as cwd** — the
`--directory "C:/..."` form silently 404'd everything once; `curl -o /dev/null -w
"%{http_code}"` catches that in one call. Add `?v=N` to defeat Chrome's cache.
Stop the server by its task id, never by name.

Two browser-tool traps:
- Images with `loading="lazy"` report `naturalWidth = 0` until actually scrolled
  into view. Set `img.loading='eager'` and wait ~3 s before believing a 0×0.
- The JS bridge returns `[BLOCKED: Cookie/query string data]` on some pages
  regardless of the URL. Fall back to a screenshot, or check the file directly.

**Python closure trap**, cost three attempts: an augmented assignment (`u += L`,
`TMP *= f`) inside a function makes that name local. Use `np.add(a, b, out=a)`
for module-level buffers.

## How to work (essentials)

- Ponytail full is the default: smallest change that works, stdlib and installed
  deps first, delete over add. `numpy`, `scipy`, `PIL` and `matplotlib` are all
  installed — do not add a dependency.
- Non-trivial logic leaves one runnable check behind. Both `demo.py` and
  `sweep.py` have `--selftest`; extend the existing one rather than adding a file.
- **Refactors of the verdict path get a regression check**, not a code read.
  Stage 2's `.txt` and `.png` were confirmed byte-identical before and after the
  track-return refactor, at 64 px / 2000 steps (~1 min each way).
- Commit when the user says so. Do not commit speculatively.
