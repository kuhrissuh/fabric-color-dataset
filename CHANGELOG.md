# Changelog

Release-level changes to the `fabric-color-dataset` repo. Per-line data changes live in `data/<manufacturer>/<line>.changelog.md`; this file rolls them up into the versions consumers pin to via jsDelivr.

Format follows [Keep a Changelog](https://keepachangelog.com/) loosely. Versions follow [semver](https://semver.org/) per the rules in [CLAUDE.md](CLAUDE.md) and [docs/project-plan.md](docs/project-plan.md).

## Unreleased

## 0.2.0 — 2026-04-19

Adds Art Gallery Fabrics Pure Solids as the second line in the dataset.

### New fabric lines
- **Art Gallery Fabrics — Pure Solids** (215 colors) — cotton, algorithmic-only hex extraction. AGF publishes flat rendered swatches rather than fabric photography, so the vision pipeline is not exercised on this line; hex values come from LAB-median sampling of the published swatch images.

### Data quality
- Kona Cotton: 96 colors flagged low-confidence (carried over from v0.1.0; no changes in this release).
- Pure Solids: confidence buckets not applicable (algorithmic-only; see line notes).

Pinned URLs:
- `https://cdn.jsdelivr.net/gh/kuhrissuh/fabric-color-dataset@v0.2.0/data/art-gallery-fabrics/pure-solids.json`
- `https://cdn.jsdelivr.net/gh/kuhrissuh/fabric-color-dataset@v0.2.0/data/robert-kaufman/kona-cotton.json`

## 0.1.0 — 2026-04-18

First public release.

### New fabric lines
- **Robert Kaufman — Kona Cotton** (370 colors) — cotton, 4.35 oz/sq yd, 44" wide. Vision-consensus hex extraction (Claude vision + algorithmic LAB-median, with ΔE-based confidence buckets).

### Data quality
- 96 colors flagged low-confidence. Per [CLAUDE.md](CLAUDE.md), these are acceptable approximations, not errors; no manual overrides pending as of release.

Pinned URL:
- `https://cdn.jsdelivr.net/gh/kuhrissuh/fabric-color-dataset@v0.1.0/data/robert-kaufman/kona-cotton.json`
