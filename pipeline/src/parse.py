"""Dispatch per-manufacturer HTML extraction."""

from __future__ import annotations

from typing import Callable, Dict, List

from models import FetchedColor, LineConfig, ParsedColor
from scrapers import art_gallery_fabrics, robert_kaufman

Scraper = Callable[[bytes, FetchedColor, LineConfig], ParsedColor]

_SCRAPERS: Dict[str, Scraper] = {
    "robert_kaufman": robert_kaufman.parse,
    "art_gallery_fabrics": art_gallery_fabrics.parse,
}


def parse(
    fetched: List[FetchedColor], config: LineConfig
) -> List[ParsedColor]:
    scraper = _SCRAPERS.get(config.scraper)
    if scraper is None:
        raise ValueError(
            f"no scraper registered for {config.scraper!r}; "
            f"known: {sorted(_SCRAPERS)}"
        )

    out: List[ParsedColor] = []
    for item in fetched:
        html_bytes = item.html_path.read_bytes()
        out.append(scraper(html_bytes, item, config))
    return out
