"""Art Gallery Fabrics Pure Solids catalog extractor.

AGF publishes every Pure Solids color on a single catalog page rather than
giving each color a product page of its own. Each color appears as a gallery
item with a rendered swatch image plus a `title="SKU Name"` attribute on its
fancybox anchor. Example catalog entries:

    <a class="fancybox info" href=".../PE-594-Storm_500px.jpg" title="PE-594 Storm">
    <a class="fancybox info" href=".../PES900-Monet.jpg" title="PES900 Monet">
    <a class="fancybox info" href=".../PES919-Truffle.jpg" title="PES919-Truffle">

SKU formatting is inconsistent — sometimes `PE-594`, sometimes `PE582`,
sometimes `PES900`. The separator between SKU and name is usually a space
but occasionally a hyphen (observed: PES919-Truffle). The regex handles
both.

Because the same catalog URL is returned for every color, the fetch stage's
per-run URL dedupe avoids downloading the catalog 45 times.
"""

from __future__ import annotations

import re
import time
from typing import List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from models import DiscoveredColor, FetchedColor, LineConfig, ParsedColor

_USER_AGENT = (
    "fabric-color-dataset/0.1 "
    "(+https://github.com/karissawhobson/fabric-color-dataset)"
)
_REQUEST_TIMEOUT = 30
_RETRIES = 2
_RETRY_BACKOFF_SECONDS = 2

# title attribute: {SKU}{sep}{NAME}. SKU: PE-###, PE###, or PES###. Separator:
# whitespace OR a single hyphen. Name: rest.
_TITLE_RE = re.compile(
    r"^\s*(?P<sku>PE[S]?-?\d+)[\s\-]+(?P<name>[^\"]+?)\s*$"
)


class ParseError(Exception):
    pass


def discover(config: LineConfig) -> List[DiscoveredColor]:
    catalog_url = config.product_url_template
    html = _http_get(catalog_url)
    entries = _parse_catalog_entries(html)
    if not entries:
        raise ParseError(
            f"no Pure Solids gallery entries found at {catalog_url} — "
            f"site markup may have changed"
        )
    return [
        DiscoveredColor(sku=sku, product_url=catalog_url, image_url=img_url)
        for sku, _name, img_url in entries
    ]


def parse(
    html_bytes: bytes, fetched: FetchedColor, config: LineConfig
) -> ParsedColor:
    entries = _parse_catalog_entries(html_bytes)
    name = _find_name(entries, fetched.sku)
    if name is None:
        raise ParseError(
            f"{fetched.sku}: no matching title found in catalog HTML"
        )
    return ParsedColor(
        sku=fetched.sku,
        name=name,
        product_url=fetched.product_url,
        image_url=fetched.image_url,
        image_path=fetched.image_path,
        image_sha256=fetched.image_sha256,
        fetched_on=fetched.fetched_on,
    )


def _parse_catalog_entries(
    html: bytes,
) -> List[Tuple[str, str, str]]:
    """Return list of (sku, name, image_url) parsed from the catalog HTML."""
    soup = BeautifulSoup(html, "html.parser")
    out: List[Tuple[str, str, str]] = []
    for a in soup.find_all("a"):
        classes = a.get("class") or []
        if "fancybox" not in classes:
            continue
        href = a.get("href", "")
        title = a.get("title", "")
        if not href or not title:
            continue
        if "/wp-content/uploads/" not in href or not href.endswith(".jpg"):
            continue
        match = _TITLE_RE.match(title)
        if not match:
            continue
        sku = match.group("sku")
        name = _clean_name(match.group("name"))
        out.append((sku, name, href))
    return out


def _find_name(
    entries: List[Tuple[str, str, str]], sku: str
) -> Optional[str]:
    for entry_sku, name, _ in entries:
        if entry_sku == sku:
            return name
    return None


def _clean_name(raw: str) -> str:
    return re.sub(r"\s+", " ", raw).strip().title()


def _http_get(url: str) -> bytes:
    session = requests.Session()
    session.headers["User-Agent"] = _USER_AGENT
    last: Optional[Exception] = None
    for attempt in range(_RETRIES + 1):
        try:
            response = session.get(url, timeout=_REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.content
        except requests.RequestException as exc:
            last = exc
            if attempt < _RETRIES:
                time.sleep(_RETRY_BACKOFF_SECONDS * (attempt + 1))
    raise RuntimeError(f"failed to fetch {url}: {last}")
