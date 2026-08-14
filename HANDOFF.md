# HANDOFF — resume point for reaction-diffusion-simulation

**Read this first each new session, then `PLAN.html` for the full spec.**
This file is the live "what to do next"; `PLAN.html` is the standing plan.
There is no repo-level `CLAUDE.md` — standing conventions come from the global
`~/.claude/CLAUDE.md`.

Last updated **2026-08-13**, after E1 and E2 ran and the docs were rewritten.
**E1 found a glider — the project's central question is answered.**

This file is kept *current, not cumulative*: superseded plans are pruned here.
That is the opposite of the rule for the prose docs, where every superseded claim
is **corrected in place, never deleted**. `documentation.html` is the full
archaeological record; this file is only the resume point.

## Current state

- **`demo.py`, commit `1eef904`** — two Gray-Scott demos with generated audio.
  Config `a` = coral (`f=0.0545, k=0.062`), `b` = mitosis (`f=0.0367, k=0.0649`).
  **Unmodified by all sweep work and must stay that way** — `sweep.py` imports it
  only as the reference its selftest checks against.
- **`sweep.py`** — the whole parameter sweep, plus E1/E2. Modes: `--stage1`,
  `--stage2`, `--ratio` (stage 3), `--stage4`, `--stage5`, `--e1`, `--e2`,
  and `--selftest` (**six checks, all passing**).
- **All five stages and both experiments have run. Do not re-run any of them.**
  Stages 2, 4 and 5 are null results, now fully explained. E1 passes.
- **GitHub Actions, commit `e57048e`** — `.github/workflows/claude.yml` and
  `claude-code-review.yml`. Opening a PR triggers a review. Simon does not
  normally use PRs.

### ⚠️ Uncommitted work — the last commit is `e2f649f`

The E1/E2 result and the doc rewrite are **on disk but not committed**. Simon's
convention is *commit only when he says so*, and he had not said so when the
session ended. Six modified, two added:

```
 M .gitignore  HANDOFF.md  PLAN.html  README.md  documentation.html  sweep.py
 ?? sweep_e1_du164_film.png  sweep_e1_du300_scaled_film.png
```

The two PNGs are **deliberately tracked** — `README.md` embeds them — via `!`
negation lines in `.gitignore`. Every other `sweep_*` output stays ignored and
regenerable. `sweep_preview.jpg` was previously the only tracked sweep image.

**Ask before committing. If he says go: one commit covering all eight paths.**

### What changed in the docs (2026-08-13, uncommitted)

- `documentation.html` **5.80 → 5.85 MB**. New section `#result`, "The result — a
  glider, in 0.6 minutes", both filmstrips inlined as JPEG, plus a `Resolution`
  group in the contents rail. In `#gap` the `Du` row is demoted and both
  "untested" rows are struck and closed. In `#bridge` the E1 and E2 cards record
  what actually happened.
- `README.md` — new section "The glider, and what actually blocked it", three ✅
  correction blocks, and the E1/E2 commands in Quick start.
- `PLAN.html` — E1 and E2 status rows (total compute now **177.5 min**), a
  scaling-trap card under *Three axes, not four*, and closures on two
  *Known risks* bullets.
- Verified: rendered at `127.0.0.1:8771`, **11 images load, 0 broken, 0 dead
  anchors**, tag balance checked on a base64-stripped copy.

## Next task

**E3 — vary `(f, k)` and the seed, outward from the working point.** The working
point is now known and reproducible, so E3 is a perturbation study, not a hunt.
Start from `run_e1`'s configuration and change one knob at a time.

- Any new scan must keep the **live `v=0.3` background** — that is precisely what
  stages 2, 4 and 5 lacked.
- Extend `k` past `0.0640`. Stage 2's strongest soliton band is at `k=0.0655`,
  outside every window searched so far.
- Munafo's published band is `0.0608833 ≤ k ≤ 0.0609829` at `f=0.06`. Mapping
  this solver's band against it is the natural first result.

⚠️ **Any run that changes `Du` must also stretch the grid by `√(Du/0.164)`.**
Otherwise it measures the scaling artifact E2 walked into, not the knob it meant
to. `sweep.py --e1 --du X --scaled` does this.

**Batch before looping.** `run_e1` is single-tile at ~0.34 ms/step. `Du`, `f` and
`k` can all become `(T,1,1)` arrays through `step_batch` — about five lines in
`run_e1` — which would run a whole perturbation grid in one pass. Do that if E3
needs more than ~20 runs.

Two live warnings:
1. **Budget from a measured step rate at the actual array shape.** Never scale a
   benchmark by tile count and pixel area — that is how stage 5's estimate came
   out 2.1× low.
2. **A soup field defeats centroid tracking.** `_ang` follows one structure, not
   fifty. Keep single-structure seeds, or add blob detection first.

If the user asks for something else, that takes precedence.

## Where to read things (reference, don't re-derive)

- `documentation.html` — the long-form write-up. `#result` is the current state
  of the glider question; `#found`, `#gap`, `#missed`, `#bridge` are the audit.
- `PLAN.html` — spec for stages 1–3 plus a status table of every outcome against
  its prediction. Stages 4, 5, E1 and E2 were added after it was written and
  appear only in its status table.
- `demo.py:37-42` — the 9-point Laplacian. `demo.py:63-68` — the reaction step
  and the `[0,1]` clip.
- `sweep.py` — `run_e1` / `e1_seed` / `E1_RECTS` are the working recipe;
  `glider_verdicts` is the shared glider test; `tail_metrics` is stage 2's.

## Facts already established — do not re-derive

### E1 — the glider, and the recipe that produces it

- ✅ **E1 PASSES.** One tile, 128×64 periodic, 100 000 steps, **0.6 min** at
  0.34 ms/step. Mass held to **−0.10%** over the second 50 000 steps, `fill_max`
  **0.115**, speed **1.344 px per 1000 steps**. It travels left, crosses the wrap
  edge near step 50 000, and returns with its shape intact. `python sweep.py --e1`.
- **The recipe**, from `Patterns/GrayScott1984/U-Skate/Munafo_glider.vti` in
  `github.com/GollyGang/ready` (2.5 KB of XML). `Du=0.164, Dv=0.082, f=0.062,
  k=0.06093`, `dt=1`, 128×64 periodic; `u=0.5` **and** `v=0.3` everywhere, then
  `v=0` in three rectangles at grid fractions `(0.40,0.62)-(0.56,0.74)`,
  `(0.40,0.40)-(0.56,0.52)`, `(0.48,0.50)-(0.56,0.62)`. Backing paper:
  R. P. Munafo, arXiv:1501.01990.
- **Three implicit knobs were read out of Ready's source, not assumed.** Boundary
  is **periodic** (`AbstractRD.cpp:215` defaults `wrap` true; the `.vti` sets no
  attribute). Stencil factor is **exact** — `stencils.cpp:499` is
  `RotationallySymmetric3x3(1,4,-20)/6`, and `KERN` is `0.3 ×` it, so a Ready `D`
  divides by 0.3 to become a repo `D`. Rectangles have **no off-by-one** —
  `overlays.cpp:631` tests `index/N` inclusive from 0, giving x∈[52,71] and
  y∈[26,33],[32,39],[40,47], **380 cells**. The last two are asserted in
  `--selftest`.
- **Both formerly untested knobs are discharged and neither mattered.** Pre-clip
  `max(u,v)` peaks at **0.9819**, so the `[0,1]` clip never fires; E1 runs
  unclipped anyway (`step_batch(..., clip=False)`). `--f64` reproduces every
  figure to four decimals.
- **The live background needed new metrics; the verdict logic did not change.**
  With `v=0.3` everywhere, `v.sum()` is nearly all background and `(v>0.1).mean()`
  is 1.0 at step 0, so `glider_verdicts` would have called a perfect glider
  "worm-filled". `run_e1` feeds it `|v − median(v)|` instead, which reduces to
  plain `v` when the background is dead — the stage 2 case. `glider_verdicts` is
  untouched.
- `run_stage2` could **not** be reused, despite an earlier plan here saying so:
  the non-square grid breaks `_ang`/`th`/`render_grid`, `u = where(v>0, 0.5, 1.0)`
  is wrong when only chemical `b` is overwritten, and the metrics above.
  `run_e1` is a separate ~55-line function. `render_grid` was generalised to
  non-square tiles and `step_batch` gained `clip=True`; both defaults leave
  stages 1–5 unchanged.

### E2 — `Du` was never the blocker, and the first answer was wrong

- ⚠️ **The scaling trap, and the single most useful thing in this file.**
  Gray-Scott is **scale-invariant**: scaling both `D` by λ is exactly a spatial
  stretch by √λ. So raising `Du` on a **fixed** grid shrinks the domain *and the
  seed* relative to the structure. E2 first walked `Du` at a fixed 128×64 and
  reported a ceiling at `Du_ready ≈ 0.2735` — **an artifact.** It measured the
  seed leaving the skater's basin. `sweep_e2_du_walk.txt` holds that table;
  the number in it is not a ceiling.
- ✅ **The real ceiling, grid stretched by √(Du/0.164):** `Du_ready` between
  **0.340 and 0.350**, repo `Du` between **1.133 and 1.167**. `E1_RECTS` are
  fractions, so the seed rescales for free. Measured at 60 000 steps:
  0.274 → 165×83 **GLIDER** (died at fixed scale); **0.30 → 173×87 GLIDER**
  (mass −0.09%, speed 1.846); 0.32 → GLIDER; 0.34 → GLIDER (mass 116.5,
  grow +0.0001, speed 1.972); 0.35 → 187×93 **soliton**; ≥0.370 → `inf`.
- ⚠️ **So this repo's own `Du = 1.0` (Ready's 0.30) DOES support the glider**, at
  173×87. It sits below the 1.133–1.167 ceiling. Stages 2, 4 and 5 were **not**
  searching a region where the structure cannot exist.
- **The divergence at `Du_ready ≥ 0.370` confirms the Euler bound.** Repo
  `Du = 1.233` against the `D·dt < 1.25` limit the −1.6 eigenvalue predicts. The
  glider ceiling sits just under that, so it is most likely accuracy loss as
  `D·dt` approaches stability, not physics.

### The three nulls, and the one cause

- **Stage 2: 0 gliders in 154 tiles.** 14 `(f,k)` pairs × 11 seeds, 192 px,
  10 000 steps, 25.0 min. 28 soliton, 51 grew, 75 unsettled. Symmetric seeds
  (single, and all 8 blob pairs) produced **exactly zero** travel — a symmetric
  seed has no direction to travel in. Only `asym` moved.
- **Stage 4: 0 gliders of 4.** The four stage-2 near-misses, `asym` only, 192 px,
  40 000 steps, 1.6 min. All gain mass monotonically: +47%, +56%, +88%, +199%
  across the second half.
- **Stage 5: 0 gliders and 0 solitons of 162.** `k` 0.0600→0.0640 at `Δk = 5e-5`,
  `f = 0.0620` and `0.0682`, `asym` seed, 160 px, 20 000 steps, **72.9 min**.
  Two regimes, nothing between.
- ✅ **All three have one cause: the initial condition.** A dead `(1, 0)`
  background with `v` **raised** in the wrong shape, instead of a live `(0.5,0.3)`
  background with `v` **lowered** in the right one. Different basin of
  attraction; no `(f, k)` scan crosses between basins. Stage 5 eliminated `k`
  resolution; E2 eliminated `Du`; E1 supplied the working seed.
- **Domain size was not the blocker for stages 2 and 4** — their 192 px strictly
  exceeds the 173×87 shown to work. Stage 5's **160 px** is close to 173 on the
  travel axis and stays **undemonstrated**; leave that one open.
- ✅ **The published `(f, k)` transfer exactly.** This was recorded as "the
  assumption under test" for most of the project's life and is now settled by E1.
  Munafo's Table 1 band is `0.0608833 ≤ k ≤ 0.0609829` at `f=0.06`, moving under
  `6e-6` across three grid refinements — so stage 5's `Δk = 5e-5` comb was
  correctly sized, and **2 of its 162 tiles sat inside that band**. It stood on
  the target for 72.9 minutes with the seed wrong.
- **Stage 2's own table already proved seed-dependence and was never read that
  way.** At `f=0.0682, k=0.0632`: `single` → soliton, `asym` → worm. Same
  coordinates, different attractor.

### Verdict-metric traps (all still live)

- **A flat `v.sum()` is not evidence of a glider.** Twice the flattest mass curves
  in a run were structures that had filled the domain — the ten flattest in
  stage 5 all have `fill` between 0.775 and 1.000. That is what the
  `fill_max > 0.35` cut catches. Always read the fill track.
- **Flatness is a spread, not an endpoint difference.** A curve that rises then
  falls has near-zero endpoint change; a 300-step trial once scored 11 such curves
  as conserved gliders. `glider_verdicts` gates on `(max−min)/mean` over the
  second half.

### Numerics and performance

- The 9-point Laplacian's most negative eigenvalue is **−1.6**, so explicit Euler
  is stable for `D·dt < 1.25`. `D_u = 1.0` is at 80% of that.
- `scipy.ndimage.convolve(Z, K, mode="wrap")` with
  `K = [[.05,.2,.05],[.2,-1,.2],[.05,.2,.05]]` matches `demo.laplacian` to
  **2.2e-16** and is **5× faster** than eight `np.roll` calls. Measured: 144 tiles
  at 192 px float32, **149 ms/step** vs 774 ms/step.
- ⚠️ **Never scale a benchmark across array shapes.** Stage 5 was budgeted at 35
  min this way and ran **2.1× over** (~219 ms/step). Measure at the real shape.
- Measured rates: stage 1, 146 tiles at 192 px, 8000 steps, float32 = **21.3 min**.
  E1 at its real 1×64×128 shape = **0.34 ms/step**, unclipped, `check=True` every
  step.
- **Total compute: five stages 162.5 min, E1+E2 under 15 min.**

### The map

- `mean |Δv|` falls in **three** bands, not two: **> 1e-4** genuinely dynamic (the
  low-`f` corner); **1e-7 to 1e-5** static solitons; **0** filled or dead. Coral
  (3.5e-05) and mitosis (4.4e-05) sit between bands. `DYN = 1e-4` is a rough cut;
  read the number, not the colour.
- **Stage 3, three ratios.** At 0.3: 142 of 146 live, 3 soliton-like. At 0.5: 104
  live, 13 soliton-like. At 0.7: 68 live, 6 soliton-like, and **coral and mitosis
  both die**. No new pattern class at any ratio. **Ratio 0.5 has the widest
  bistable window.** Do not re-run stage 3.
- The demo MP4s run **longer** than the sheet: coral 25 200 steps, mitosis 16 800.

## Session-transient scratch (regenerate; durable record is the committed file)

**Downloads are gone after a clear. Re-fetch, do not re-derive:**

```bash
curl -s https://raw.githubusercontent.com/GollyGang/ready/master/Patterns/GrayScott1984/U-Skate/Munafo_glider.vti
curl -s https://raw.githubusercontent.com/GollyGang/ready/master/src/readybase/stencils.cpp   # stencil at :499
curl -s https://raw.githubusercontent.com/GollyGang/ready/master/src/readybase/overlays.cpp   # rectangle test at :631
curl -s https://raw.githubusercontent.com/GollyGang/ready/master/src/readybase/AbstractRD.cpp # wrap default at :215
```

Everything those files contain is now encoded in `run_e1` and asserted in
`--selftest`, so a re-fetch is only needed to check a *new* claim about Ready.

The paper (arXiv:1501.01990) is a PDF; `pdftoppm` is **not** installed, so `Read`
cannot open it. `pymupdf` **is** — use `fitz.open(path)` with
`PYTHONIOENCODING=utf-8`, or the ligature `ﬁ` raises `UnicodeEncodeError` on
cp1252. The `ar5iv.labs.arxiv.org/html/...` mirror is easier and worked first try.

Benchmarks were throwaway `python -c "..."` one-liners; nothing on disk. The
durable record is the table in `PLAN.html`.

**Figure/section pipeline for `documentation.html`** — throwaway, run from the
scratchpad. Used twice now; the pattern, if more sections are needed:

1. Write the section HTML with a `{{PLACEHOLDER}}` per figure.
2. Downscale the PNG with `PIL.Image.thumbnail((1000,1000))`, save JPEG
   `quality=90, optimize=True`, base64-encode, substitute. The two E1 films came
   out at 15 KB and 17 KB.
3. Insert before `<footer class="page">`. **Match the anchor with a
   whitespace-tolerant regex** — `re.compile(r'</section>\s*<footer class="page">')`
   — and assert exactly one match. A literal `'</section>\n\n<footer…'` broke on
   the second insert.
4. **Write with `open(path, "w", encoding="utf-8", newline="")`.** Plain
   `Path.write_text` translates `\n` to `\r\n` on Windows and churns the file.
5. For in-place corrections, `assert s.count(old) == 1` on every anchor before
   replacing. Cheap, and it caught nothing this time only because it was there.
6. Check tag balance by counting `<tag` against `</tag>` on a copy with base64
   payloads stripped (`re.sub(r'(base64,)[A-Za-z0-9+/=]+', ...)`) — that also
   makes the 5.85 MB file readable at ~79 KB.

To change a figure, edit the committed `documentation.html` directly rather than
rebuilding this pipeline.

**Rendering check.** `file://` URLs are refused by the browser tool. Serve with
`python -m http.server <port> --bind 127.0.0.1` **from the repo as cwd** — the
`--directory "C:/..."` form silently 404'd everything once; `curl -o /dev/null -w
"%{http_code}"` catches that in one call. Add `?v=N` to defeat Chrome's cache.
**Stop the server by the PID holding the port**, never by name:
`Get-NetTCPConnection -LocalPort <port> -State Listen` → `Stop-Process -Id`.

Three browser-tool traps:
- Images with `loading="lazy"` report `naturalWidth = 0` until scrolled into view.
  Set `img.loading='eager'` and wait ~3 s before believing a 0×0.
- The JS bridge returns `[BLOCKED: Cookie/query string data]` on some pages
  regardless of URL. Fall back to a screenshot.
- **Setting `scrollTop` via JS silently does nothing on `documentation.html`** —
  it reports 71 and stays there. Scroll with the `computer` tool's `scroll`
  action or the `End` key instead.

**Python closure trap**, cost three attempts: an augmented assignment (`u += L`,
`TMP *= f`) inside a function makes that name local. Use `np.add(a, b, out=a)`
for module-level buffers.

**Encoding trap**, cost one round trip: `sweep.py` must stay readable as cp1252.
A `⚠️` (U+26A0) in a code comment breaks `open(path, encoding='cp1252')` even
though Python itself reads the file as UTF-8. Use ASCII `WARNING:` in `.py`
files. Markdown and HTML are fine. Check with
`sorted({hex(ord(c)) for c in s if ord(c) > 127})` — `sweep.py` should show only
`0x2014`.

## How to work (essentials)

- Ponytail full is the default: smallest change that works, stdlib and installed
  deps first, delete over add. `numpy`, `scipy`, `PIL` and `matplotlib` are all
  installed — do not add a dependency.
- Non-trivial logic leaves one runnable check behind. Both `demo.py` and
  `sweep.py` have `--selftest`; extend the existing one rather than adding a file.
- **Refactors of the verdict path get a regression check**, not a code read.
  Stage 2's `.txt` and `.png` were confirmed byte-identical across the
  track-return refactor, at 64 px / 2000 steps.
- **In the prose docs, correct in place — never delete.** Strike the old claim,
  state the new one beside it, say what changed. That convention is why the E2
  artifact is still visible in all three files rather than quietly removed.
- Commit when the user says so. Do not commit speculatively.
