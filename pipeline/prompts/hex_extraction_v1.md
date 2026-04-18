# Hex extraction prompt — v1

Version: 1
Created: 2026-04-18

## Changelog
- v1 (2026-04-18): Initial version for the Kona Cotton calibration pass.

---

You are examining a photograph of a solid-color quilting cotton fabric swatch.
The fabric is uniformly dyed. Identify the single hex color that best represents
the fabric as it would appear under neutral daylight to a human looking at a
physical bolt in a well-lit fabric store.

Ignore anything that is not the fabric itself: page backgrounds, tags, text
overlays, shadows along edges, selvedges, and any specular highlights from the
photographer's lighting. Focus on the central fabric area where the weave fills
the frame.

If the fabric clearly shows fine weave texture, average across the texture —
do not pick the color of a single thread.

If you cannot determine a clear dominant color (e.g., the image is not a
fabric swatch, the swatch is not solid, lighting is unusable, or the image is
corrupted), set `confidence` to `"low"` and describe what you see in
`observations`. Do not guess.

Respond with a single JSON object, no prose before or after, matching exactly
this shape:

```json
{
  "hex": "#RRGGBB",
  "confidence": "high" | "medium" | "low",
  "observations": "one short sentence describing what you see",
  "warnings": ["short phrase per issue, empty list if none"]
}
```

Rules for the fields:
- `hex` must be an uppercase 6-digit sRGB hex string starting with `#`.
- `confidence`:
  - `"high"`: swatch is clearly a uniformly lit solid fabric, no notable
    artifacts, you are confident in the color.
  - `"medium"`: color is identifiable but there are visible artifacts (shadows,
    slight color cast, uneven lighting, heavy texture).
  - `"low"`: cannot determine a dominant color; see note above.
- `observations`: one short descriptive sentence. Do not mention the hex value.
- `warnings`: short noun phrases for specific issues you noticed
  ("shadow on left edge", "visible selvedge", "uneven lighting"). Empty list
  if there are no issues.
