# Schema v1

JSON Schema describing the shape of a fabric color line file. Consumers pin on `schema_version` and can rely on backward compatibility within a major version. See [STABILITY.md](../STABILITY.md) for the full compatibility contract.

The authoritative definition is [`v1.json`](./v1.json). This document explains each field.

A separate schema, [`index_v1.json`](./index_v1.json), describes [`/data/index.json`](../data/index.json) — the manifest listing every line file in the dataset. Each entry mirrors the per-file header (`manufacturer_slug`, `line_slug`, `manufacturer_name`, `line_name`, `path`, `color_count`, `data_version`) so consumers can render a picker without fetching every line file.

---

## File-level fields

### `schema_version`

Semver of the schema shape (`^\d+\.\d+\.\d+$`). Consumers pin on this. Additive changes bump minor; removals or renames bump major. For this schema: `"1.0.0"`.

### `data_version`

Semver of this file's content. Bumps whenever the color list changes.

- Patch: hex correction, URL fix, metadata correction.
- Minor: new colors added, colors marked discontinued.
- Major: reserved for schema migrations; does not normally occur within a file.

### `manufacturer`

Object describing the manufacturer of this fabric line.

- `name` — display name (e.g. `"Robert Kaufman"`).
- `slug` — URL-safe identifier used in color IDs and the filesystem path (e.g. `"robert-kaufman"`). Lowercase, hyphen-separated, `^[a-z0-9]+(-[a-z0-9]+)*$`. Spelled out to stay self-documenting; there is no separate short form.
- `website` — manufacturer's homepage.

### `line`

Object describing the specific fabric line.

- `name` — display name (e.g. `"Kona Cotton"`).
- `slug` — URL-safe identifier used in color IDs (e.g. `"kona-cotton"`).
- `substrate` — fabric type, lowercase (e.g. `"cotton"`).
- `weight_oz_per_sq_yd` — fabric weight, imperial. Positive number.
- `width_inches` — bolt width, imperial. Positive number.

### `notes`

One to three sentences of neutral factual context about the line. Not marketing copy, not care instructions. Empty string allowed if no notable context.

### `id_scheme`

How color IDs in this file were constructed. One of:

- `manufacturer_sku` — ID derives from the manufacturer's SKU (the common case).
- `name_slug` — ID derives from a slugified color name (used when the manufacturer does not publish clean SKUs).

### `generated_on`

ISO 8601 date (`YYYY-MM-DD`) of the pipeline run that last produced this file. No timestamps — sub-day precision lives in git history.

### `generator_version`

Semver of the pipeline that produced this file. Separate from `data_version` so the process can evolve independently of the data.

### `color_count`

Integer, equal to `colors.length`. Redundant but useful for sanity-checking downloads and for readable diffs.

### `colors`

Array of per-color records (see below).

---

## Per-color fields

### `id`

Permanent identifier for this color. Format: `{manufacturer.slug}-{line.slug}-{slugified(sku)}`. Lowercase, hyphen-separated.

**An ID refers to the same color forever.** Never renamed, never reassigned. This is the one immutable commitment in the dataset.

### `name`

Display name. Can change; the `id` does not follow.

### `sku`

Manufacturer SKU as printed on the source page (e.g. `"K001-197"`). Preserved as its own field so consumers need not parse IDs.

### `aliases`

Array of strings for the "we need to rename but can't change the ID" case. Empty by default. Consumer search UIs should match on both `name` and `aliases`.

### `hex`

Primary hex value. Uppercase, sRGB, `^#[0-9A-F]{6}$`. This is the one field most consumers will use.

### `hex_method`

How `hex` was determined. One of:

- `manufacturer_official` — published by the manufacturer as a hex or swatch-with-spec.
- `vision_claude` — extracted by a vision model alone.
- `algorithmic` — computed by LAB-median extraction alone.
- `vision_consensus` — vision and algorithmic agreed (ΔE < 3).
- `manual_override` — corrected by a human. Persists across pipeline runs unless the source image hash changes.

### `hex_confidence`

Quality bucket. One of `high`, `medium`, `low`. Determined by ΔE distance in LAB space between vision and algorithmic extractions:

- `high` — ΔE < 3 and no warnings from the vision model.
- `medium` — ΔE < 3 with warnings, or 3 ≤ ΔE < 7.
- `low` — ΔE ≥ 7. Flagged for human review.

Three buckets rather than a float — floats imply false precision and push threshold decisions onto every consumer.

### `hex_algorithmic`

The deterministic LAB-median extraction, stored alongside `hex` as cross-check evidence. Same format as `hex`.

### `hex_source`

Where the swatch image came from.

- `image_url` — direct URL to the swatch image on the manufacturer's site.
- `image_sha256` — SHA-256 of the downloaded image bytes. The keystone field: detects when a manufacturer swaps a swatch photo, and serves as the cache key for vision extraction.

### `manufacturer_product_url`

The authoritative product page for this color on the manufacturer's site.

### `status`

Lifecycle state. One of:

- `active` — currently produced.
- `discontinued` — manufacturer has removed it; record retained for referential integrity.
- `unknown` — status cannot be determined from public information.
- `superseded` — replaced by another record (rare; used when an ID must be corrected via the alias mechanism).

Colors are never hard-deleted. Designs built against old data need stable references.

### `first_seen`

ISO 8601 date. The date this color first appeared in the dataset. Never updates.

### `source_collected_on`

ISO 8601 date. The date of the most recent pipeline run in which this color's data was refreshed. Updates only when the record actually changes.

---

## Derivable values not in the schema

Intentionally omitted; computable in one line of code:

- `hex_rgb`, `hex_hsl`, `hex_lab` — convert from `hex`.
- Color families or tags — deferred until a QA process exists.

---

## Validation rules beyond JSON Schema

The validator in [`pipeline/src/validate.py`](../pipeline/src/validate.py) enforces the schema plus structural rules that JSON Schema cannot express:

1. `color_count == colors.length`.
2. Every color `id` equals `{manufacturer.slug}-{line.slug}-{slugified(sku)}`.
3. All color IDs are unique within a file.
4. For each color, `first_seen <= source_collected_on <= generated_on`.

Cross-file rules (ID stability between runs, no hard-deletes) belong to the merge stage, not the schema.
