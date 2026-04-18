"""Produce the list of color URLs to fetch for a line."""

from __future__ import annotations

from typing import List

from models import DiscoveredColor, LineConfig


def discover(config: LineConfig) -> List[DiscoveredColor]:
    """Expand the config SKU list into full product + image URLs.

    For v0.1 the SKU list is hardcoded in the YAML. A future version may
    crawl a manufacturer index page here.
    """
    out: List[DiscoveredColor] = []
    for sku in config.skus:
        out.append(
            DiscoveredColor(
                sku=sku,
                product_url=config.product_url_template.format(sku=sku),
                image_url=config.image_url_template.format(sku=sku),
            )
        )
    return out
