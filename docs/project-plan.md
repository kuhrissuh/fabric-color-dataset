# fabric-color-dataset — Project Plan

An open-source fabric color dataset. Structured JSON files mapping real fabric colors (name, SKU, hex) to their source manufacturer pages. The repo is the product — versioned JSON files that other tools (web apps, iOS apps, quilt design tools) depend on as a data layer.

**First target:** Robert Kaufman Kona Cotton (~370 colors).

Art Gallery Fabrics Pure Solids was the initial candidate but was deferred. AGF publishes flat rendered color blocks rather than fabric photography, which defeats the purpose of the vision-extraction pipeline. Kona uses real fabric photography (visible weave), so the pipeline is exercised end-to-end; adding AGF later as an algorithmic-only line is then a straightforward additive step.

The core principle running through every decision below: **build the smallest version that does the thing, defer everything speculative, optimize for the case where you're the only user for a while.** The schema and the stability contract are load-bearing; most other infrastructure is not.

A chronological index of key decisions (what was chosen, why, alternatives rejected) lives in [`docs/decisions.md`](decisions.md). When making tradeoff calls, check there first — many questions have already been settled.

---

## Schema

The schema is the API. Downstream tools pin to it, so it deserves the most care.

### Per-color record

```json
{
  "id": "robert-kaufman-kona-cotton-k001-197",
  "name": "Aloe",
  "sku": "K001-197",
  "aliases": [],
  "hex": "#7ED3B0",
  "hex_method": "vision_consensus",
  "hex_confidence": "high",
  "hex_algorithmic": "#7BD1AE",
  "hex_source": {
    "image_url": "https://...",
    "image_sha256": "a3f2..."
  },
  "manufacturer_product_url": "https://...",
  "status": "active",
  "first_seen": "2026-04-17",
  "source_collected_on": "2026-04-17"
}
```

**Field rationale:**

- **`id`** — `{manufacturer-slug}-{line-slug}-{sku}`, lowercased. Permanent for the life of the project. The one truly immutable commitment. Self-contained (a consumer storing only the ID can always locate the color).
- **`name`** — display name. Can change; ID doesn't follow.
- **`sku`** — manufacturer SKU. The part that went into the ID, preserved as its own field for consumers that don't want to parse IDs.
- **`aliases`** — array for the "we need to rename but can't change the ID" case. Empty by default.
- **`hex`** — primary value, uppercase, `^#[0-9A-F]{6}$`, sRGB. The one thing most consumers will actually use.
- **`hex_method`** — enum: `manufacturer_official` | `vision_claude` | `algorithmic` | `vision_consensus` | `manual_override`. Extensible.
- **`hex_confidence`** — enum: `high` | `medium` | `low`. Three buckets with documented criteria (see Vision Extraction below). Deliberately not a float — floats imply false precision and force consumers to pick thresholds anyway.
- **`hex_algorithmic`** — the deterministic LAB-median extraction, stored as cross-check evidence alongside the primary hex.
- **`hex_source`** — `image_url` and `image_sha256`. The hash is the keystone: it detects when the manufacturer swapped a swatch photo, and it's the cache key for extraction.
- **`manufacturer_product_url`** — authoritative source page.
- **`status`** — enum: `active` | `discontinued` | `unknown` | `superseded`. Never hard-delete; soft-delete preserves referential integrity for designs built against old data.
- **`first_seen`** — date this color first appeared in the dataset. Never updates.
- **`source_collected_on`** — date of the last full pipeline run that re-collected this color. Updates only when data actually changes.

**Rule:** all time fields are ISO 8601 dates (`YYYY-MM-DD`), never timestamps. Sub-day precision is available in git history if ever needed, and keeping it out of the data files keeps diffs meaningful.

**Derivable values not in the schema:** `hex_rgb`, `hex_hsl`, `hex_lab`. Computable in one line of code in any language. Storing them creates opportunities for drift.

### File-level record

```json
{
  "schema_version": "1.0.0",
  "data_version": "0.1.0",
  "manufacturer": {
    "name": "Robert Kaufman",
    "slug": "robert-kaufman",
    "website": "https://www.robertkaufman.com"
  },
  "line": {
    "name": "Kona Cotton",
    "slug": "kona-cotton",
    "substrate": "cotton",
    "weight_oz_per_sq_yd": 4.35,
    "width_inches": 44
  },
  "notes": "Robert Kaufman's flagship solid cotton line. Oeko-tex certified. The most widely used solid in US quilting.",
  "id_scheme": "manufacturer_sku",
  "generated_on": "2026-04-17",
  "generator_version": "0.1.0",
  "color_count": 370,
  "colors": [ ... ]
}
```

**Field rationale:**

- **`schema_version`** — shape of the file. Consumers pin on this. Additive changes bump minor; removals or renames bump major.
- **`data_version`** — content of this specific file. Bumps whenever colors change.
- **`manufacturer`** and **`line`** — info shared across every color in the file. Per-color records only carry the URL that varies.
- **`notes`** — one to three sentences of neutral factual context about the line. Not marketing copy, not care instructions, not opinions.
- **`id_scheme`** — how IDs in this file were constructed. `manufacturer_sku` for Kona; future lines may use `name_slug` if the manufacturer doesn't publish clean SKUs.
- **`generated_on`** — date the pipeline last produced this file.
- **`generator_version`** — version of the pipeline. Separate from `data_version` because the process can change independently of the data.
- **`color_count`** — redundant with `colors.length` but useful for sanity-checking downloads and for readable diffs ("we went from 370 to 371").

**Units:** imperial (`weight_oz_per_sq_yd`, `width_inches`). Matches the quilting domain. When a European line is eventually added, convert to imperial for consistency within the dataset.

**Not in the file-level record:**
- Changelog — lives in sibling `.changelog.md` files, not JSON.
- Checksums — belong in the distribution layer (npm integrity, git tags), not in the file.
- Contributor attribution — git history handles this.

---

## Repo structure

Monorepo. The wall between `/data` and `/pipeline` is load-bearing: data consumers should be able to ignore everything except `/data` and `/schemas` and have a complete product.

```
fabric-color-dataset/
├── README.md
├── LICENSE-DATA          (CC0)
├── LICENSE-CODE          (MIT)
├── STABILITY.md          (the contract — what we promise consumers)
├── CHANGELOG.md          (repo-level; data changes live in per-file changelogs)
│
├── schemas/
│   ├── v1.json           (JSON Schema for the file format)
│   └── README.md         (field-by-field documentation)
│
├── data/
│   └── robert-kaufman/
│       ├── kona-cotton.json
│       └── kona-cotton.changelog.md
│
├── configs/
│   └── robert-kaufman/
│       └── kona-cotton.yaml
│
├── pipeline/
│   ├── README.md
│   ├── pyproject.toml
│   ├── src/
│   │   ├── discover.py
│   │   ├── fetch.py
│   │   ├── parse.py
│   │   ├── vision.py
│   │   ├── extract_algorithmic.py
│   │   ├── merge.py
│   │   ├── validate.py
│   │   └── scrapers/
│   │       └── art_gallery_fabrics.py
│   ├── prompts/
│   │   └── hex_extraction_v1.md
│   └── tests/
│
├── raw/                  (git-lfs: snapshot HTML + swatch images)
│   └── robert-kaufman/
│       └── kona-cotton/
│           ├── html/
│           └── images/
│
├── docs/
│   ├── vision-prompt.md
│   ├── adding-a-fabric-line.md
│   └── architecture.md
│
└── .github/
    └── workflows/
        ├── weekly-update.yml
        ├── validate-pr.yml
        └── release.yml
```

**Key structural decisions:**

- **Two license files.** `LICENSE-DATA` (CC0) for `/data` and `/schemas`. `LICENSE-CODE` (MIT) for `/pipeline` and `/configs`. Downstream tools vendoring the JSON have different obligations than those forking the scraper.
- **`STABILITY.md` as its own document.** Not buried in the README. Signals that stability is a commitment, not a suggestion.
- **`/schemas` as a peer of `/data`.** The JSON Schema is itself a product. When v2 comes, `v2.json` lives beside `v1.json` and old consumers keep validating forever.
- **`/data` organized manufacturer/line.** One level of namespacing matches how people think about fabrics. Flat breaks on name collisions; deeper is over-engineering.
- **Per-file changelogs** (`kona-cotton.changelog.md`) sit next to data files. Git has the raw diff; the changelog has the *why*.
- **`/configs` separate from `/pipeline`.** The lever for scaling contributions: adding a new line should ideally mean writing YAML, not Python. Custom logic goes in `pipeline/src/scrapers/` as a documented exception.
- **`/raw` for source snapshots via git-lfs.** Enables reproducibility (re-run vision on the same bytes when the prompt improves) and audit trail. For v0.1, LFS in-repo is simpler than external storage; migrate if it becomes a problem.

**Deliberately not included:**
- `examples/` directory. Link to real consumer projects in the README once they exist.
- `scripts/` for one-off tasks. They accumulate and rot. Real tasks go in `pipeline/` as proper subcommands.
- `vendor/` or `third-party/`. Link or fetch at runtime; don't copy data in.

---

## Pipeline architecture

**Guiding principle:** each stage is a typed function with a content-addressable cache. Re-running the pipeline only does work when something actually changed.

```
┌─────────────┐    ┌─────────┐    ┌────────┐    ┌─────────────┐
│  Discover   │───▶│  Fetch  │───▶│  Parse │───▶│   Extract   │
│ (URLs from  │    │ (HTML + │    │ (name, │    │ (vision +   │
│   config)   │    │ images) │    │  SKU)  │    │ algorithmic)│
└─────────────┘    └─────────┘    └────────┘    └─────────────┘
                                                        │
                         ┌──────────────────────────────┘
                         ▼
                  ┌──────────┐    ┌──────────┐    ┌─────────┐
                  │  Merge   │───▶│ Validate │───▶│  Write  │
                  │ (w/ prior│    │ (schema) │    │ (file + │
                  │  state)  │    │          │    │ change- │
                  │          │    │          │    │  log)   │
                  └──────────┘    └──────────┘    └─────────┘
```

### Stages

1. **Discover** — from line config, enumerate color product URLs. Cache: 1-day TTL. Output: list of URLs.
2. **Fetch** — download HTML + swatch images, store in `/raw`, compute `image_sha256`. Cache by URL + ETag/Last-Modified.
3. **Parse** — extract name, SKU, swatch image reference from HTML via per-manufacturer extractor. Cache by HTML content hash.
4. **Extract** — vision + algorithmic in parallel, then consensus. Cache key: `image_sha256 + prompt_version + algorithmic_version`. This is the critical cache — it's what makes prompt iteration cheap.
5. **Merge** — combine fresh records with existing data file, preserve stable IDs and `first_seen`, apply status transitions, compute diff. No cache.
6. **Validate** — JSON Schema + custom rules (IDs didn't change, required fields, hex format). Fails loud. No cache.
7. **Write** — updated JSON, appended changelog entry, bumped `data_version`.

### Typed boundaries

Every stage is a function with Pydantic models (or dataclasses) for input and output. No dicts across stage boundaries. When a field changes, the type checker identifies every stage that needs to update.

```python
def extract(image: FetchedImage, config: ExtractConfig) -> ExtractionResult: ...
```

### Caching

One cache directory at `~/.cache/fabric-color-dataset/{stage}/{content_hash}.json`. Each stage checks before work, writes after. Content hashes incorporate stage version; bumping a version invalidates that stage's cache automatically. In CI, persisted via GitHub Actions cache.

**Cache is local, not committed.** Committed caches bloat the repo and produce noisy diffs. `/raw` snapshots handle reproducibility; derived caches don't need to be in the repo.

### Orchestration

Plain Python CLI. No workflow framework (Airflow, Prefect, etc.). The dependency graph is linear, scale is small, and frameworks add surface area that outlasts the reason for adopting them.

```
fabric-colors run --line robert-kaufman/kona-cotton
fabric-colors run --all
fabric-colors run --line robert-kaufman/kona-cotton --stage extract --force
```

### Error handling

Two categories:

- **Transient** (network timeout, rate limit, 503): retry with backoff, fail the stage for that item, continue with others. "Scraped 369/370 colors; K001-1234 failed, will retry next run."
- **Structural** (parse failure on a previously-working page, validation failure, non-hex extraction result): fail loud, halt the pipeline, no write. These indicate a site change or pipeline bug; silent continuation corrupts data.

Test: **can this error resolve itself on retry?** Yes = transient. No = structural.

---

## Vision extraction

This is where dataset quality lives or dies.

### The goal

Not colorimetric accuracy — **consistent, reproducible, reasonable approximations.** A quilter visualizing a design needs colors that look right relative to each other and recognizably like the fabric. They don't need ΔE < 2 against a spectrophotometer.

### Pre-processing

Deterministic, cheap, applied identically to both vision and algorithmic extraction:

1. **Center crop** to middle 60–70%. Kills edges, shadows, selvedge, tags.
2. **Downscale** to 512px on long edge. Claude doesn't need more, and downscaling averages out texture noise.
3. **Sanity-check uniformity.** Standard deviation across cropped region; if too high, swatch probably isn't solid — flag for review.

### Algorithmic extraction (cross-check)

Convert cropped image to LAB color space, take channel-wise median, convert back to sRGB. LAB is perceptually uniform, so the median corresponds to "the middle color a human would see." Fast, free, deterministic. Works well on clean swatches; fails predictably on heavily textured fabrics.

### Vision prompt

Stored as versioned file: `pipeline/prompts/hex_extraction_v1.md`. Structure, not cleverness.

**Core elements:**

- Role/context framing: "This is a fabric swatch from a solid-color quilting cotton line. The fabric is uniformly dyed. Identify the hex that best represents the fabric as it would appear under neutral daylight."
- Explicit ignores: "Ignore any background, tags, text overlays, shadows, or selvedge. Focus on the central fabric area."
- Structured output (JSON only):
  ```
  {
    "hex": "#8B4513",
    "confidence": "high" | "medium" | "low",
    "observations": "brief description of what you see",
    "warnings": ["shadow on left edge", ...]
  }
  ```
- Anti-hallucination framing: "If you cannot determine a clear dominant color, set confidence to 'low' and describe what you see. Do not guess."

**Not in the prompt:**
- Examples of good outputs (risks bias toward those specific hexes).
- Color theory lectures (the model has this).
- Brand references (risks brand bias).

### Prompt versioning

The prompt file has a version in its filename and a changelog at its head. The pipeline hashes the file and uses the hash in the extraction cache key. Editing the prompt means creating `hex_extraction_v2.md` alongside v1, not modifying v1. The cache key changes, everything re-extracts, old values persist in git history.

### Model and settings

- Use the most capable Claude vision model available when implementing (check current lineup; don't rely on a specific model name from an older plan).
- Extraction is deterministic by design, not creative writing. On Opus 4.7+ the `temperature` parameter is deprecated and the API rejects it; don't pass it. On older models that still accept it, set to 0.

### Consensus logic

Two hex values come in (`hex_vision`, `hex_algorithmic`); one goes out with a confidence bucket.

```
ΔE = color_distance_LAB(hex_vision, hex_algorithmic)

if ΔE < 3 and no warnings:
    hex = hex_vision
    method = "vision_consensus"
    confidence = "high"
elif ΔE < 3 and warnings:
    hex = hex_vision
    method = "vision_consensus"
    confidence = "medium"
elif 3 <= ΔE < 7:
    hex = hex_vision
    method = "vision_claude"
    confidence = "medium"
elif ΔE >= 7:
    hex = hex_vision          # vision usually wins on disagreement
    method = "vision_claude"
    confidence = "low"        # flagged for human review
```

ΔE thresholds come from color science: < 2.3 is "just noticeable difference"; < 3 is "basically agree"; > 7 is "clearly different."

"Vision wins on disagreement" is deliberate: the algorithmic method fails predictably on textured fabrics where human-perceived color differs from mathematical median. When they disagree, it's usually the algorithm that's wrong — but confidence drops, so a human should look.

### Human review loop

`confidence: "low"` entries appear in the weekly PR description. You eyeball the swatch, pick the right value (or override manually). Manual overrides are recorded as `hex_method: "manual_override"` and persist — they don't get overwritten on subsequent runs unless the source image hash changes.

### Cost

Rough estimate at Kona Cotton scale (370 colors):

- Initial extraction: ~370 vision calls. Well under $10 at current Claude pricing.
- Weekly runs: near-zero (cache hits everywhere).
- Prompt version bumps: full re-extraction, same as initial.

Cost is a non-issue. The constraint is quality.

### Calibration

Before running on all 370, run a calibration pass on 10–15 colors with known-trustworthy swatches (mix of dark neutrals, saturated, pastels, one tricky one). Extract, eyeball against sources, tune the prompt. Then run the full set.

---

## Update cadence

**Weekly run only.** No daily liveness check for v0.1 — the week of latency on catching URL rot is genuinely fine at current scale, and the complexity cost of a second scheduled job outweighs the benefit.

**Schedule:** Monday ~4am UTC. Full pipeline. If data changed, open a PR with a diff summary and low-confidence flags.

### Auto-merge policy

**Nothing in `/data` auto-merges.** Every data change gets human review. 30 seconds of time per week to skim and click merge; the payoff is that every commit to main has had eyes on it, and consumers can trust it.

### Halt thresholds

Pipeline detects anomalies and halts instead of opening a PR:

```
if hex_change_rate > 20%:
    halt("suspicious hex change rate — manual investigation needed")
if low_confidence_rate > 10%:
    halt("suspicious confidence drop — manual investigation needed")
```

Better to halt unnecessarily and investigate than to auto-open a PR that corrupts the dataset if skim-merged.

### PR description template

Skimmable in under a minute:

```
## Weekly update — 2026-04-17

### Summary
- Added 2 new colors (Kona Cotton 2026 release)
- 1 color marked discontinued
- 3 hex values updated (manufacturer swatch photo changes)
- 0 colors flagged for review

### Added
- `robert-kaufman-kona-cotton-k001-9001` "Apricot Dream" — hex #F4A9...

### Discontinued
- `robert-kaufman-kona-cotton-k001-9002` "Vintage Rose"

### Hex updates
- `robert-kaufman-kona-cotton-k001-9003` "Caramel": #8B4513 → #8C4614 (ΔE=0.8)

### Low-confidence (review needed)
None this run.

### Validation
All checks passed.
```

### Changelog and versioning

Pipeline auto-appends to per-file `.changelog.md` on each merged update. `data_version` semver:

- **Patch**: hex corrections, URL fixes, metadata corrections.
- **Minor**: new colors added, colors marked discontinued.
- **Major**: never under normal operation — reserved for schema migrations.

### Release process

Decoupled from weekly updates. Manual tag push when stable; `release.yml` workflow handles publishing. Might merge three weekly PRs and cut one release.

---

## Distribution

**v0.1: jsDelivr CDN only.**

```
https://cdn.jsdelivr.net/gh/yourname/fabric-color-dataset@v0.1.0/data/robert-kaufman/kona-cotton.json
```

- Free, fast, globally cached, versioned by git tag.
- No publishing infrastructure to maintain (no npm/PyPI accounts, tokens, release workflows yet).
- The `@v0.1.0` pins to an immutable tagged version; `@main` fetches latest (dev only).

**Deferred to when a real consumer asks:**
- npm package (with TypeScript types generated from JSON Schema).
- PyPI package (with optional helper module).

Same principle as the daily liveness check: don't build infrastructure for hypothetical users.

### Versioning spine

- Git tags are canonical: `v0.1.0`, `v0.2.0`, etc. Immutable once created.
- jsDelivr picks up tags automatically.
- Stay on v0.x until the schema has been used by at least one real downstream consumer for ~a month without needing changes. No rush — v0.x is a legitimate state.

### Not doing

- **No REST API.** Whole new thing to run, secure, scale. CDN + (eventually) packages cover every realistic need.
- **No docs website.** README + schema docs + changelog is enough. A color browser is a downstream tool, not infrastructure.
- **No multi-registry publishing.** One per language ecosystem, when the time comes.
- **No backporting to old major versions.** Old tags are immutable. Consumers on v1 get v1 data forever; migrating means moving to v2.

---

## Stability contract (STABILITY.md)

What consumers can rely on. Roughly:

> **Within a major version:** schema is backward-compatible. New fields may be added; existing fields, their types, and their semantics will not change. New colors may be added; existing colors will not be removed or have their IDs changed.
>
> **Across major versions:** breaking changes are allowed, announced ≥30 days in advance, accompanied by a migration guide. Previous major version continues to receive data updates for 90 days after the new major ships.
>
> **Color IDs are permanent across all versions.** An ID refers to the same color for the lifetime of the project. The `aliases` field and `status: superseded` mechanism handle the rare case where an ID needs to be corrected.

### What counts as what

- **Patch**: correcting wrong data (wrong hex, typo, broken URL).
- **Minor**: adding fields, adding colors, adding lines.
- **Major**: removing fields, renaming fields, changing field types, changing field semantics, adding new enum values that change consumer code behavior (e.g., adding a fourth `hex_confidence` bucket).

### The one permanent commitment

Color IDs. Everything else can evolve through the versioning process.

---



---

## Explicitly deferred

Things we discussed and deliberately left out, so "why isn't this here?" has a clear answer:

- **Retailer URLs.** Not scraped major retailers (Fat Quarter Shop etc.); not community-contributed local shops. Maybe community-sourced local shops in a future version if demand emerges, but no placeholder field in the schema — adding cleanly later is better than reserving a shape we haven't thought through.
- **Color family / tags.** Deferred until there's a sustainable QA process. Unverifiable data is worse than no data.
- **`last_verified` / `manufacturer_product_url_last_verified` fields.** Dropped after realizing the daily liveness check wasn't happening in v0.1; `source_collected_on` covers the data-freshness question sufficiently.
- **Daily liveness check.** Weekly latency on URL-rot detection is fine at current scale.
- **npm and PyPI packages.** jsDelivr only until a real consumer asks.
- **REST API, docs website, color browser UI.** Each is a project unto itself.
- **Auto-merging of data changes.** Every data PR gets human review.
- **CONTRIBUTING.md, issue templates, and contributor infrastructure.** Replaced with a single line in the README: *"This project is in early development and not actively accepting external contributions yet. Bug reports and data corrections are welcome via GitHub issues."* Revisit when there's actual contributor interest.
- **`hex_samples` (palette of sampled points per color).** Level-2 schema (primary hex + metadata) for now. Level 3 (palette) is a pure additive change later if a consumer needs it.
- **Workflow orchestration framework.** Plain Python until scale genuinely requires otherwise.
- **Derivable color values** (`hex_rgb`, `hex_hsl`, `hex_lab`). One line of code in any language.
- **Timestamps in data files.** Dates only, for clean diffs.

---

## Build order for v0.1

1. Set up the repo skeleton (READMEs, LICENSE files, STABILITY.md, `schemas/v1.json`, empty data directory, pipeline scaffolding).
2. Write the JSON Schema and a validator.
3. Build the Kona scraper end-to-end for 10–15 calibration colors — hardcode URLs, get the full pipeline working on a small set.
4. Tune the vision prompt against the calibration set until results look right.
5. Run on all 370 colors, review low-confidence entries, ship v0.1.0 with jsDelivr distribution.
6. Use it in one downstream tool yourself.

Step 6 is the most important. Consuming your own dataset is how you find out whether the schema is actually good. Every schema looks fine in the abstract; only use reveals what's missing or awkward.

### Key reminders during the build

- **The calibration pass is non-negotiable.** Don't skip to running all 370.
- **Slow read of the schema once more before generating data against it.** Changing the schema after v0.1.0 with real consumers costs real work.
- **Your own consumer is the most important consumer.** Prioritize getting to step 6 even if the dataset feels rough.
- **Ship the good version, not the perfect one.** Everything here is designed to evolve; the stability contract exists so you can ship now and change later.
