"""Per-manufacturer HTML extractors.

Each scraper exposes a `parse(html_bytes, fetched, config) -> ParsedColor`
function. The parse stage dispatches on `config.scraper` to the right one.
"""
