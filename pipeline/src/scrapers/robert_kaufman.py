"""Robert Kaufman product-page extractor.

Target layout (as of 2026-04):
    <meta property="og:title" content="K001-197 ALOE  from Kona® Cotton" />
    <h1 class='page_title'>... K001-197 ALOE  from <a>Kona® Cotton</a> ...</h1>

We pull the color name from the og:title tag (same text as the h1, but with
markup already stripped). The SKU is verified to match the expected value so
a site-wide HTML change fails loudly instead of mis-labeling a color.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from models import FetchedColor, LineConfig, ParsedColor

_TITLE_RE = re.compile(
    r"""^\s*
        (?P<sku>[A-Z0-9][A-Z0-9-]*)   # SKU
        \s+
        (?P<name>.+?)                 # color name (possibly multi-word)
        \s+from\s+                    # literal "from"
        (?P<line>.+?)                 # line name
        \s*$""",
    re.VERBOSE | re.IGNORECASE,
)


class ParseError(Exception):
    pass


def parse(
    html_bytes: bytes, fetched: FetchedColor, config: LineConfig
) -> ParsedColor:
    soup = BeautifulSoup(html_bytes, "html.parser")

    raw = _og_title(soup) or _h1_text(soup)
    if raw is None:
        raise ParseError(f"{fetched.sku}: neither og:title nor h1.page_title found")

    match = _TITLE_RE.match(raw)
    if not match:
        raise ParseError(
            f"{fetched.sku}: title {raw!r} did not match expected "
            f"'SKU NAME from LINE' pattern"
        )

    found_sku = match.group("sku").upper()
    if found_sku != fetched.sku.upper():
        raise ParseError(
            f"{fetched.sku}: title SKU {found_sku!r} does not match "
            f"expected {fetched.sku!r} (site markup may have changed)"
        )

    name = _clean_name(match.group("name"))

    return ParsedColor(
        sku=fetched.sku,
        name=name,
        product_url=fetched.product_url,
        image_url=fetched.image_url,
        image_path=fetched.image_path,
        image_sha256=fetched.image_sha256,
        fetched_on=fetched.fetched_on,
    )


def _og_title(soup: BeautifulSoup) -> str | None:
    for tag in soup.find_all("meta", attrs={"property": "og:title"}):
        content = tag.get("content", "").strip()
        if " from " in content and content.split()[0].upper().startswith("K"):
            return content
    return None


def _h1_text(soup: BeautifulSoup) -> str | None:
    h1 = soup.find("h1", class_="page_title")
    if not h1:
        return None
    return h1.get_text(" ", strip=True)


def _clean_name(raw: str) -> str:
    collapsed = re.sub(r"\s+", " ", raw).strip()
    # Title case — Kaufman uppercases everything (ALOE, HONEY DEW); the
    # dataset convention is title case.
    return collapsed.title()
