"""Produce the list of color URLs to fetch for a line.

Two strategies:

- Most manufacturers expose a predictable per-SKU URL for the product page
  and its swatch image. The default discoverer expands the config SKU list
  using `url_templates.product` and `url_templates.image`.
- Some manufacturers publish all colors on a single catalog page with no
  per-SKU URLs (e.g. Art Gallery Fabrics Pure Solids). Those scrapers
  register a custom discoverer that scrapes the catalog live and returns
  one DiscoveredColor per color found there. Custom discoverers may issue
  HTTP requests.
"""

from __future__ import annotations

from typing import Callable, Dict, List

from models import DiscoveredColor, LineConfig
from scrapers import art_gallery_fabrics, riley_blake_designs

Discoverer = Callable[[LineConfig], List[DiscoveredColor]]

_CUSTOM_DISCOVERERS: Dict[str, Discoverer] = {
    "art_gallery_fabrics": art_gallery_fabrics.discover,
    "riley_blake_designs": riley_blake_designs.discover,
}


def discover(config: LineConfig) -> List[DiscoveredColor]:
    custom = _CUSTOM_DISCOVERERS.get(config.scraper)
    if custom is not None:
        return custom(config)

    if config.image_url_template is None:
        raise ValueError(
            f"scraper {config.scraper!r} has no custom discoverer and the "
            f"config is missing url_templates.image"
        )
    return [
        DiscoveredColor(
            sku=sku,
            product_url=config.product_url_template.format(sku=sku),
            image_url=config.image_url_template.format(sku=sku),
        )
        for sku in config.skus
    ]
