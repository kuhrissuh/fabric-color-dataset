"""Riley Blake Designs Confetti Cottons catalog extractor.

Riley Blake's site is backed by a NetSuite SCA cacheable-items JSON API:

    /api/cacheable/items?c=4582045&commercecategoryurl=...&limit=100&offset=N

The `c` and `commercecategoryurl` parameters pin the response to the
Confetti Cottons category. `limit` is capped server-side at 100 (the server
returns HTTP 400 on higher values); discover paginates by rewriting the
`offset=0` token in `config.product_url_template` to offset=100, 200, etc.

The category contains 410 items — 300 base colors plus precuts, 20-yard
bolts, and swatch cards. The canonical filter for base colors is a plain
regex on `itemid`: `^C120-[A-Z0-9]+$`.

Each base item has a `storedisplayname` of the form `"Confetti Cotton™ {Name}"`,
a `urlcomponent` like `"Confetti-Cotton-{Name}"`, and an `itemid` like
`"C120-{NAME}"`. Images live under a predictable path; the API returns
URLs with unencoded spaces, so the scraper builds image URLs directly
from itemid with %20 rather than round-tripping through the API value.

DiscoveredColor.product_url is set to the offset-specific API URL so fetch
dedupes repeated downloads — one fetch per 100 items. parse() re-parses the
same JSON bytes and rewrites product_url to the canonical per-color URL
`https://www.rileyblakedesigns.com/{urlcomponent}`, which is what consumers
see in the final data file.
"""

from __future__ import annotations

import json
import re
import time
from typing import List, Optional

import requests

from models import DiscoveredColor, FetchedColor, LineConfig, ParsedColor

_PAGE_SIZE = 100
_MAX_PAGES = 20

_BASE_COLOR_SKU_RE = re.compile(r"^C120-[A-Z0-9]+$")
_NAME_PREFIX_RE = re.compile(r"^Confetti\s+Cotton(?:™)?\s+")
_PRODUCT_URL_ROOT = "https://www.rileyblakedesigns.com"
_IMAGE_URL_TEMPLATE = (
    "https://www.rileyblakedesigns.com/assets/Product%20Images/{itemid}_media-1.jpg"
)

_USER_AGENT = (
    "fabric-color-dataset/0.1 "
    "(+https://github.com/karissawhobson/fabric-color-dataset)"
)
_REQUEST_TIMEOUT = 30
_RETRIES = 2
_RETRY_BACKOFF_SECONDS = 2


class ParseError(Exception):
    pass


def discover(config: LineConfig) -> List[DiscoveredColor]:
    base_url = config.product_url_template
    if "offset=0" not in base_url:
        raise ParseError(
            f"product URL template must contain `offset=0`; got {base_url!r}"
        )

    seen: set[str] = set()
    out: List[DiscoveredColor] = []
    expected_total: Optional[int] = None

    for page in range(_MAX_PAGES):
        offset = page * _PAGE_SIZE
        page_url = base_url.replace("offset=0", f"offset={offset}", 1)
        payload = _parse_json(_http_get(page_url))

        if expected_total is None:
            expected_total = int(payload.get("total", 0))
            if expected_total == 0:
                raise ParseError(
                    f"no Confetti Cottons items reported at {base_url} — "
                    f"API shape may have changed"
                )

        for item in payload.get("items", []):
            itemid = item.get("itemid", "")
            if not _BASE_COLOR_SKU_RE.match(itemid):
                continue
            if itemid in seen:
                continue
            seen.add(itemid)
            out.append(
                DiscoveredColor(
                    sku=itemid,
                    product_url=page_url,
                    image_url=_IMAGE_URL_TEMPLATE.format(itemid=itemid),
                )
            )

        if offset + _PAGE_SIZE >= expected_total:
            return out

    raise ParseError(
        f"pagination did not terminate within {_MAX_PAGES} pages at {base_url} — "
        f"expected_total={expected_total}, collected={len(out)}"
    )


def parse(
    html_bytes: bytes, fetched: FetchedColor, config: LineConfig
) -> ParsedColor:
    payload = _parse_json(html_bytes)
    item = _find_item(payload, fetched.sku)
    if item is None:
        raise ParseError(
            f"{fetched.sku}: not present in fetched JSON batch"
        )

    name = _extract_name(item)
    urlcomponent = item.get("urlcomponent") or ""
    if not urlcomponent:
        raise ParseError(f"{fetched.sku}: missing urlcomponent in API response")

    return ParsedColor(
        sku=fetched.sku,
        name=name,
        product_url=f"{_PRODUCT_URL_ROOT}/{urlcomponent}",
        image_url=fetched.image_url,
        image_path=fetched.image_path,
        image_sha256=fetched.image_sha256,
        fetched_on=fetched.fetched_on,
    )


def _parse_json(body: bytes) -> dict:
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise ParseError(f"could not decode Riley Blake JSON: {exc}")


def _find_item(payload: dict, sku: str) -> Optional[dict]:
    for item in payload.get("items", []):
        if item.get("itemid") == sku:
            return item
    return None


def _extract_name(item: dict) -> str:
    raw = item.get("storedisplayname", "")
    stripped = _NAME_PREFIX_RE.sub("", raw).strip()
    if not stripped:
        raise ParseError(
            f"could not extract color name from storedisplayname={raw!r}"
        )
    return re.sub(r"\s+", " ", stripped)


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
