# fabric-color-dataset

An open-source fabric color dataset. Structured JSON files mapping real fabric colors (name, SKU, hex) to their source manufacturer pages. The repo is the product — versioned JSON that web apps, iOS apps, and quilt design tools can depend on as a data layer.

**First target:** Art Gallery Fabrics Pure Solids (~203 colors).

## Using the data

Files are available via jsDelivr CDN, pinned to a git tag:

```
https://cdn.jsdelivr.net/gh/kwoodwardhobson/fabric-color-dataset@v0.1.0/data/art-gallery-fabrics/pure-solids.json
```

Use `@main` for the latest (unreleased) data.

## Stability

See [STABILITY.md](STABILITY.md) for the full stability contract — what you can rely on across versions.

## Licensing

- `/data` and `/schemas` — [CC0 1.0 Universal](LICENSE-DATA) (no rights reserved)
- `/pipeline` and `/configs` — [MIT](LICENSE-CODE)

## Contributing

This project is in early development and not actively accepting external contributions yet. Bug reports and data corrections are welcome via GitHub issues.
