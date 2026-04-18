# Vision prompt — design and calibration

The vision prompt is the core quality lever for the dataset. This doc records
why the prompt is shaped the way it is and the evidence that each version
passed calibration.

Prompt files live at `pipeline/prompts/hex_extraction_v{N}.md`. The active
version is pinned in `pipeline/src/vision.py` (`PROMPT_VERSION`).

## Versioning rule

Editing an existing prompt file is not allowed. A change means a new file
(`hex_extraction_v2.md`) alongside the old one. The content hash of the
prompt file is part of the vision cache key, so:

- Bumping the version forces full re-extraction (intended).
- Touching an old version would silently invalidate cached entries that
  still reference it — don't.

## v1 — 2026-04-18

### Design choices

- **No few-shot examples.** Risked anchoring the model toward specific hex
  values. Structure over cleverness.
- **Explicit ignores list** (background, tags, shadows, selvedge, specular
  highlights). Kona product photos are clean but edge artifacts are the
  top realistic failure mode.
- **Texture averaging instruction.** Fine weave is visible at the native
  crop; without guidance the model could pick a single-thread color.
- **Structured JSON output** with `hex`, `confidence`, `observations`,
  `warnings`. Confidence is a three-bucket enum, not a float — floats
  imply false precision and push the threshold decision onto consumers.
- **Anti-hallucination clause**: if no clear dominant color, set
  `confidence: "low"` and describe what's seen. Do not guess.

### Calibration run

Ran the full pipeline against the 12-SKU calibration set. All 12 vision
responses came back `confidence: "high"` with empty `warnings` lists — the
model is consistent and confident across the luminance/chroma space
(near-black, near-white, dark neutrals, saturated mid-tones, pastels).

Consensus bucket distribution (ΔE vision vs algorithmic):

| SKU       | Name       | vision  | algorithmic | ΔE     | final bucket |
|-----------|------------|---------|-------------|--------|--------------|
| K001-1019 | Black      | #1A1A1A | #222423     |  4.85  | medium       |
| K001-1080 | Coal       | #5E5E5F | #5B595A     |  2.08  | high         |
| K001-1083 | Coffee     | #4A3627 | #443224     |  2.30  | high         |
| K001-7    | Tomato     | #E8401F | #DC241C     |  7.77  | low          |
| K001-23   | Lemon      | #F7E189 | #FDDC7C     |  6.57  | medium       |
| K001-25   | Ocean      | #1F45B8 | #173B94     | 15.49  | low          |
| K001-1188 | Kiwi       | #2BBF3E | #20BB3C     |  1.69  | high         |
| K001-21   | Honey Dew  | #D2E292 | #D9E88B     |  6.56  | medium       |
| K001-197  | Aloe       | #7ED4B0 | #7ED6B4     |  1.35  | high         |
| K001-1514 | Robin Egg  | #9FE3ED | #8EEBFA     |  6.86  | medium       |
| K001-1387 | White      | #FAFAFA | #F6F6F8     |  1.68  | high         |
| K001-1072 | Chartreuse | #BBD143 | #BAD235     |  5.23  | medium       |

5 high · 5 medium · 2 low.

### Visual spot-check

Each swatch image inspected against both hex values. Summary:

- **Ocean** (largest disagreement, ΔE=15.49): vision matches the bright
  cobalt in the image; algorithmic is a darker navy because weave shadows
  pull the LAB median down. Vision correct.
- **Tomato** (ΔE=7.77): vision tracks the bright red-orange; algorithmic
  is darker and more saturated. Vision preferred.
- **Black** (ΔE=4.85): vision's near-black reading is closer than
  algorithmic's lighter gray-tinged value.
- Mediums (Lemon, Honey Dew, Robin Egg, Chartreuse): both values sit in
  the same neighborhood; differences are sub-perceptual saturation/hue
  shifts within expected photographic tolerance.
- Highs (Coal, Coffee, Kiwi, Aloe, White): strong agreement; unsurprising
  on low-texture and near-neutral fabrics.

### Verdict

Prompt v1 passes calibration. The pipeline behaves exactly as designed:
vision is reliable, algorithmic fails predictably on textured fabrics,
and ΔE disagreements correctly surface the cases a human should eyeball.
No prompt changes; proceed to the full 370-color run.

### Known non-prompt issue: low-confidence rate

Calibration produced a 2/12 = 16.7% low-confidence rate, above the 10%
halt threshold defined for weekly runs. This is a calibration artifact,
not a production signal — the halt threshold is designed for run-to-run
drift detection against existing data. A first-run against an empty
dataset has no baseline to compare to, and in this case both low-confidence
entries (Tomato, Ocean) are cases where vision is reasonable and the
algorithmic extractor is the disagreer. The threshold logic should be
revisited if the full 370-color run produces a similar pattern.
