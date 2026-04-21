# Decision Log

Chronological record of design and architecture decisions for the fabric-color-dataset project. Captures *what* was decided, *why*, and what alternatives were considered. Full rationale for each decision lives in `docs/project-plan.md`; this file is the scannable index.

---

## 2026-04-20 — Per-item fetch resilience + 25% fetch-failure halt threshold

**Status:** accepted

`pipeline/src/fetch.py` now catches `FetchError` per SKU instead of raising on the first failure. Failed SKUs are collected into a `FetchFailure` list on the new `FetchResult` stage-boundary dataclass and surfaced in the run summary / PR body. Merge already carries prior records forward for SKUs missing from the fresh run, so partial runs produce a safe diff.

A third halt threshold was added alongside the existing hex-change (>20%) and low-confidence (>10%) halts: `fetch_failure_rate > 25%`. Without it, a systematic block on manufacturer IPs (hypothesis 2 in [issue #9](https://github.com/kuhrissuh/fabric-color-dataset/issues/9)) would surface as "0 material changes, skipping PR" — silently succeeding with an empty run. The threshold is deliberately loose (25%) because per-run sporadic 403s on a 370-SKU catalog should not halt the pipeline; only a systemic failure should.

Alternatives considered: (a) halt immediately after fetch instead of threading failures through to the summary. Rejected — surfacing failures in the PR body is useful even when below threshold, both for visibility and for telling the two issue-#9 hypotheses apart over a run or two. (b) catch broader exceptions than `FetchError`. Rejected — catching `RuntimeError` or bare `Exception` would mask programming errors inside the loop; a dedicated exception class keeps the resilience scope tight.

Consequence: the monthly run can now complete partial successes and produce a reviewable PR. Issue #9's recommended path (observe a run or two, distinguish sporadic vs. systematic filtering) is unblocked.

---

## 2026-04-20 — Pipeline cadence changed from weekly to monthly

**Status:** accepted

The scheduled pipeline run (formerly `weekly-update.yml`, now `monthly-update.yml`) runs on the 1st of each month at ~4am UTC instead of every Monday. Branch names, PR titles, and the concurrency group all use the `monthly-update` prefix.

Fabric manufacturers publish new lines seasonally, not weekly. A weekly cadence was always going to produce an empty PR most weeks, and the act of running the pipeline against upstream pages adds load on manufacturer sites (and on the Anthropic API for first-run-per-prompt-version cases) with no corresponding signal. Monthly is the first cadence where the probability of a material change per run is meaningfully above zero.

Daily and weekly alternatives were rejected. Daily would compound the load problem and require a liveness-check split that was already deferred (see `docs/project-plan.md` "Deliberately not included"). Weekly was the initial choice but the shipping reality of fabric catalogs doesn't warrant it — URL-rot latency at a month is still fine at current scale.

Consequence: the `0 4 * * 1` cron becomes `0 4 1 * *`. The cron remains commented out pending resolution of issue #9 (runner-model decision) — this change is a rename/reframe, not a re-enable. Historical references in this decision log to "weekly" cadence are left in place; the reasoning each entry captures still applies.

---

## 2026-04-20 — Low-confidence colors are spot-checked but never overridden

**Status:** accepted

Low-confidence colors (ΔE ≥ 7) get a manual visual spot-check to catch gross extraction failures — cases where the displayed swatch is clearly the wrong hue (e.g. green rendering where the fabric is purple). If the pipeline value is in the right ballpark, it is left as-is.

The alternative — overriding low-confidence values with manually corrected hex — was deliberately rejected. Manual overrides would make the dataset non-reproducible: a future pipeline run would disagree with the stored value, creating noise and requiring ongoing human maintenance. Leaving the pipeline value in place means every run produces the same output from the same inputs. The `low` confidence flag is the signal to consumers that the value may be approximate; it is not an invitation to patch it.

Consequence: low-confidence colors carry a known approximation error, but the dataset remains fully pipeline-reproducible. Manual overrides (`hex_method: "manual_override"`) are reserved for cases where the pipeline value is categorically wrong, not merely imprecise.

---



**Status:** accepted

Art Gallery Fabrics Pure Solids was the initial candidate. AGF was ruled out because it publishes flat rendered color blocks rather than fabric photography. The vision-extraction pipeline exists specifically to sample real woven fabric — flat renders defeat the purpose and would leave the most complex pipeline stage untested. Kona Cotton uses real fabric photography (visible weave texture), so it exercises the full pipeline end-to-end.

AGF was not dropped — it was deferred to v0.2 as an algorithmic-only line. Adding it after Kona is a straightforward additive step.

---

## 2026-04-17 — Permanent color IDs

**Status:** accepted

Format: `{manufacturer-slug}-{line-slug}-{sku}`, lowercased. Once a color is published, its ID is immutable. The ID never follows a name change; `aliases` handles the rename case.

The alternative (numeric auto-increment IDs) was rejected because it requires a central registry and breaks if two people generate IDs independently. SKU-based IDs are self-contained: a consumer storing only the ID can always locate the color without querying the dataset.

Consequence: the format must be defined before the first release and cannot be revised without a major version bump.

---

## 2026-04-17 — Dates, not timestamps, in data files

**Status:** accepted

All time fields (`first_seen`, `source_collected_on`, `generated_on`) are ISO 8601 dates (`YYYY-MM-DD`). Sub-day precision is available in git history if ever needed.

Timestamps (e.g. `2026-04-17T14:32:00Z`) would make every weekly pipeline run produce a noisy diff even when no color data changed. Date-only fields keep diffs meaningful — a changed date signals a real data update, not just a re-run.

---

## 2026-04-17 — Split license: CC0 for data, MIT for pipeline

**Status:** accepted

`/data` and `/schemas` are the product that downstream tools depend on — they are CC0 (public domain dedication) so consumers face zero license friction. `/pipeline` and `/configs` are the generator code — MIT.

Blurring the line (e.g. a single repo-wide license) would either encumber the data with code-license terms or leave the pipeline without a clear license. The split keeps the two concerns clean.

---

## 2026-04-17 — No auto-merging of data PRs

**Status:** accepted

The pipeline can open PRs against `/data` but cannot merge them. Every data PR gets human review.

Automated merges are tempting for a weekly update cycle, but the dataset is the product — a corrupt merge is a breaking change for every downstream consumer pinned to the affected version. The review step is the last safety net before data reaches jsDelivr.

---

## 2026-04-17 — Three confidence buckets, not a float

**Status:** accepted

`hex_confidence` is an enum: `high` | `medium` | `low`. The buckets are determined by ΔE distance in LAB space between vision and algorithmic extractions:
- `high`: ΔE < 3, no vision warnings
- `medium`: ΔE < 3 with warnings, OR 3 ≤ ΔE < 7
- `low`: ΔE ≥ 7

A float confidence score (e.g. 0.0–1.0) was considered and rejected. Floats imply false precision and force every consumer to independently choose a threshold. Three buckets push the threshold decision into the dataset where it can be documented and agreed on once.

---

## 2026-04-17 — Halt on anomaly, don't auto-correct

**Status:** accepted

If a pipeline run detects >20% hex changes or >10% low-confidence rate, it halts with an error rather than opening a PR.

The alternative — opening a PR and flagging the anomaly in the PR description — was rejected because it puts the burden of catching a corrupted run on the reviewer. Halting forces investigation before any data reaches the PR stage. Better to miss a weekly update than to publish bad data.

---

## 2026-04-17 — Derived color values excluded from schema

**Status:** accepted

`hex_rgb`, `hex_hsl`, `hex_lab`, and similar derived representations are not stored in the dataset. They are computable from `hex` in one line of code in any language.

Storing them creates drift risk (derived values could become inconsistent with `hex` after a manual override or correction) and adds schema fields that carry no new information. Consumers that need derived values compute them locally.

---

## 2026-04-18 — Vision prompt versioned as immutable files

**Status:** accepted

Prompt files live at `pipeline/prompts/hex_extraction_v{N}.md`. Editing an existing prompt file is not allowed — a change means creating a new file (`v2`) alongside the old one. The content hash of the prompt file is part of the extraction cache key.

This design ensures that bumping the prompt version forces full re-extraction (intended behavior) and that cached entries remain valid as long as the image hash and prompt hash are unchanged. Modifying `v1` in place would silently invalidate cached entries that still reference it.

---

## 2026-04-18 — Prompt v1 passed calibration; proceed to full run

**Status:** accepted

A 12-SKU calibration set was run against prompt v1. All 12 vision responses returned `confidence: "high"` with empty `warnings` lists. Consensus bucket distribution: 5 high · 5 medium · 2 low (ΔE-based). Visual spot-checks on the two low-confidence entries (Ocean, Tomato) confirmed vision was correct and the algorithmic extractor was the disagreer.

The 2/12 = 16.7% low-confidence rate exceeds the 10% halt threshold, but that threshold is designed for run-to-run drift detection against existing data, not a first run against an empty dataset. No prompt changes were needed. Full 370-color run authorized.

See `docs/vision-prompt.md` for the full calibration table and spot-check notes.

---

## 2026-04-19 — Art Gallery Fabrics Pure Solids added as algorithmic-only in v0.2

**Status:** accepted

AGF was deferred at v0.1 (see 2026-04-17 entry above). It was added in v0.2 as an algorithmic-only line: `hex_confidence` is not applicable, and `hex_method` is `algorithmic` for all colors. The vision pipeline is not exercised on AGF because its swatch images are flat renders rather than fabric photography.

This is the expected post-v0.1 path. No schema changes were required — the existing `hex_method` enum already included `algorithmic`, and the schema is additive. Data version bumped to 0.2.0 (new fabric line = minor bump per semver rules).
