# fabric-color-dataset

Open-source fabric color dataset. Structured JSON files mapping fabric colors (name, SKU, hex) to their source manufacturer pages. The repo is the product — other tools depend on it as a data layer.

**First target:** Robert Kaufman Kona Cotton (~370 colors).

Art Gallery Fabrics Pure Solids was the initial candidate but was deferred: AGF publishes flat rendered swatches rather than fabric photography, so the line wouldn't exercise the full vision extraction pipeline. AGF is a post-v0.1 addition as an algorithmic-only line.

Full project rationale lives in `docs/project-plan.md`. This file is operational context — constraints to remember every session.

## Load-bearing constraints

**Color IDs are permanent.** Format: `{manufacturer-slug}-{line-slug}-{sku}`, lowercased. Once published, an ID refers to the same color forever. Never rename, never reassign.

**Dates, not timestamps.** All time fields in data files are ISO 8601 dates (`YYYY-MM-DD`). Sub-day precision is available in git history if needed; keeping it out of data files keeps diffs meaningful.

**Data and code are separated.** `/data` and `/schemas` are the product (CC0 license). `/pipeline` and `/configs` are the generator (MIT license). Don't blur the line.

**No auto-merging of data changes.** Every PR touching `/data` gets human review. Pipeline can open PRs, can't merge them.

**Imperial units for fabric dimensions.** `width_inches`, `weight_oz_per_sq_yd`. Matches the quilting domain.

**Semver is strict.** Additive changes (new field, new color, new line) = minor bump. Anything that could break a consumer (removed field, renamed field, changed semantics) = major bump. Data corrections = patch.

## Pipeline principles

**Every stage is a typed function with a content-hash cache.** Stages: discover → fetch → parse → extract → merge → validate → write. Pydantic models (or dataclasses) at stage boundaries, never dicts.

**Image hash is the cache key for extraction.** Re-extraction happens only when `image_sha256` changes or when the prompt version bumps. This is what makes prompt iteration cheap.

**Halt on anomaly, don't auto-PR.** If the pipeline detects >20% hex changes or >10% low-confidence rate across a run, halt with an error. Better to investigate manually than to corrupt the dataset.

**Vision prompt is versioned as a file.** `pipeline/prompts/hex_extraction_v1.md`. Editing means creating `v2` alongside, not modifying `v1`. The file hash is part of the extraction cache key.

**Temperature 0 for vision calls.** This is extraction, not creative writing.

**Use the most capable Claude vision model available when implementing.** Don't hardcode a specific model name from an older plan; check current lineup.

## Confidence buckets

Three buckets, determined by ΔE distance in LAB space between vision and algorithmic extractions:
- `high`: ΔE < 3, no warnings from vision
- `medium`: ΔE < 3 with warnings, OR 3 ≤ ΔE < 7
- `low`: ΔE ≥ 7 — flagged for human review in the weekly PR

Manual overrides use `hex_method: "manual_override"` and persist across runs unless the source image hash changes.

## Explicitly deferred (don't add unless asked)

Things we deliberately left out. If tempted to add one, check `docs/project-plan.md` first — these are scoped out on purpose, not oversights.

- Retailer URLs (any kind — major retailers, local shops, anything)
- Color family / tags fields
- `last_verified` / `*_last_verified` fields on records
- Daily liveness check
- npm and PyPI packages (jsDelivr only for v0.1)
- REST API, docs website, color browser UI
- CONTRIBUTING.md, issue templates, CLA, code of conduct
- Derived color values (`hex_rgb`, `hex_hsl`, `hex_lab`) — computable in one line
- Workflow orchestration frameworks (plain Python is fine)
- `hex_samples` palette field (Level 2 schema only for v0.1)

## Distribution

v0.1 uses jsDelivr CDN only:
```
https://cdn.jsdelivr.net/gh/USER/fabric-color-dataset@v0.1.0/data/...
```
Git tags are immutable. Tag releases manually; don't tag on every weekly merge.

## Discipline when working on this codebase

- Keep tasks narrow. One stage, one concern per session.
- Review diffs carefully before committing.
- Push back on deviations from the plan. If something feels off against `docs/project-plan.md`, say so before implementing.
- Update this file when a constraint needs reinforcing across sessions.
