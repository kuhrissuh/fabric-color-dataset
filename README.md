# fabric-color-dataset

An open-source fabric color dataset. Structured JSON files mapping real fabric colors (name, SKU, hex) to their source manufacturer pages. The repo is the product — versioned JSON that web apps, iOS apps, and quilt design tools can depend on as a data layer.

**First target:** Robert Kaufman Kona Cotton (~370 colors).

## What the hex values are

Every `hex` in this dataset is an **approximation**. A six-digit sRGB hex cannot match a piece of dyed cotton — the fabric reflects light non-uniformly, its color shifts with viewing angle and lighting, and dyes occupy regions of color space that sRGB doesn't fully cover. The goal here is a consistent, reproducible approximation of how each fabric reads to the eye under neutral daylight, not a colorimetric match to the physical swatch.

The `hex_confidence` field is the dataset's own estimate of how close the approximation is, in three buckets:

- `high` — our vision and algorithmic extractions agree closely and the vision model had no warnings about the source image.
- `medium` — the two methods agree closely but the vision model flagged something (edge shadow, texture), or they disagree moderately.
- `low` — the two methods disagree more than usual. This does **not** mean the hex is wrong; it means the approximation has more uncertainty than a `high` entry. Use `hex_confidence` to decide how much to trust a given color for your use case.

## Using the data

Files are available via jsDelivr CDN, pinned to a git tag:

```
https://cdn.jsdelivr.net/gh/kuhrissuh/fabric-color-dataset@v0.1.0/data/robert-kaufman/kona-cotton.json
```

Use `@main` for the latest (unreleased) data.

A manifest of every line in the dataset lives at `data/index.json`, so consumers don't have to hardcode line paths:

```
https://cdn.jsdelivr.net/gh/kuhrissuh/fabric-color-dataset@v0.1.0/data/index.json
```

## Stability

See [STABILITY.md](STABILITY.md) for the full stability contract — what you can rely on across versions.

## Licensing

- `/data` and `/schemas` — [CC0 1.0 Universal](LICENSE-DATA) (no rights reserved)
- `/pipeline` and `/configs` — [MIT](LICENSE-CODE)

## Contributing

This project is in early development and not actively accepting external contributions yet. Bug reports and data corrections are welcome via GitHub issues.
