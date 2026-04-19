from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from models import FetchedColor, Line, LineConfig, Manufacturer
from scrapers import art_gallery_fabrics

CATALOG_URL = "https://liveartgalleryfabrics.com/pure-solids-quilting-cotton/"


def _fetched(sku: str = "PE-594") -> FetchedColor:
    return FetchedColor(
        sku=sku,
        product_url=CATALOG_URL,
        image_url=f"https://example.com/{sku}.jpg",
        html_path=Path(f"/tmp/{sku}.html"),
        image_path=Path(f"/tmp/{sku}.jpg"),
        image_sha256="a" * 64,
        fetched_on=date(2026, 4, 19),
    )


def _config() -> LineConfig:
    return LineConfig(
        manufacturer=Manufacturer(
            name="Art Gallery Fabrics",
            slug="art-gallery-fabrics",
            website="https://www.artgalleryfabrics.com",
        ),
        line=Line(
            name="Pure Solids",
            slug="pure-solids",
            substrate="cotton",
            weight_oz_per_sq_yd=3.92,
            width_inches=44.0,
        ),
        notes="",
        id_scheme="manufacturer_sku",
        scraper="art_gallery_fabrics",
        product_url_template=CATALOG_URL,
        image_url_template=None,
        skus=[],
    )


def _catalog_html(entries: list[tuple[str, str, str]]) -> bytes:
    """Build a minimal AGF-style catalog page from (title, href, class) triples."""
    anchors = "\n".join(
        f'<a class="{cls}" href="{href}" title="{title}">x</a>'
        for title, href, cls in entries
    )
    return f"<html><body>{anchors}</body></html>".encode()


def _fancybox(
    title: str,
    href: str = "https://liveartgalleryfabrics.com/wp-content/uploads/2020/01/img.jpg",
) -> tuple[str, str, str]:
    return (title, href, "fancybox info")


def test_parses_hyphenated_sku():
    html = _catalog_html([_fancybox("PE-594 Storm")])
    entries = art_gallery_fabrics._parse_catalog_entries(html)
    assert entries == [
        ("PE-594", "Storm", "https://liveartgalleryfabrics.com/wp-content/uploads/2020/01/img.jpg"),
    ]


def test_parses_unhyphenated_sku():
    html = _catalog_html([_fancybox("PE582 Caviar")])
    entries = art_gallery_fabrics._parse_catalog_entries(html)
    assert entries[0][0] == "PE582"
    assert entries[0][1] == "Caviar"


def test_parses_pes_prefix():
    html = _catalog_html([_fancybox("PES900 Monet")])
    entries = art_gallery_fabrics._parse_catalog_entries(html)
    assert entries[0][0] == "PES900"
    assert entries[0][1] == "Monet"


def test_parses_hyphen_separator_between_sku_and_name():
    # Observed in the wild: PES919-Truffle instead of PES919 Truffle.
    html = _catalog_html([_fancybox("PES919-Truffle")])
    entries = art_gallery_fabrics._parse_catalog_entries(html)
    assert entries[0][0] == "PES919"
    assert entries[0][1] == "Truffle"


def test_titlecases_uppercase_name():
    html = _catalog_html([_fancybox("PES900 MONET BLUE")])
    entries = art_gallery_fabrics._parse_catalog_entries(html)
    assert entries[0][1] == "Monet Blue"


def test_collapses_whitespace_in_name():
    html = _catalog_html([_fancybox("PES900  Monet   Blue")])
    entries = art_gallery_fabrics._parse_catalog_entries(html)
    assert entries[0][1] == "Monet Blue"


def test_ignores_non_fancybox_anchor():
    html = _catalog_html(
        [
            ("PE-594 Storm", "https://liveartgalleryfabrics.com/wp-content/uploads/2020/01/img.jpg", "other"),
        ]
    )
    assert art_gallery_fabrics._parse_catalog_entries(html) == []


def test_ignores_non_wp_uploads_href():
    html = _catalog_html(
        [("PE-594 Storm", "https://example.com/other/img.jpg", "fancybox info")]
    )
    assert art_gallery_fabrics._parse_catalog_entries(html) == []


def test_ignores_non_jpg_href():
    html = _catalog_html(
        [
            (
                "PE-594 Storm",
                "https://liveartgalleryfabrics.com/wp-content/uploads/2020/01/img.png",
                "fancybox info",
            )
        ]
    )
    assert art_gallery_fabrics._parse_catalog_entries(html) == []


def test_ignores_malformed_title():
    html = _catalog_html([_fancybox("not a real title")])
    assert art_gallery_fabrics._parse_catalog_entries(html) == []


def test_parses_multiple_entries():
    html = _catalog_html(
        [
            _fancybox(
                "PE-594 Storm",
                "https://liveartgalleryfabrics.com/wp-content/uploads/2020/01/a.jpg",
            ),
            _fancybox(
                "PES900 Monet",
                "https://liveartgalleryfabrics.com/wp-content/uploads/2020/01/b.jpg",
            ),
        ]
    )
    entries = art_gallery_fabrics._parse_catalog_entries(html)
    assert len(entries) == 2
    assert entries[0][0] == "PE-594"
    assert entries[1][0] == "PES900"


def test_discover_returns_one_per_entry(monkeypatch):
    html = _catalog_html(
        [
            _fancybox(
                "PE-594 Storm",
                "https://liveartgalleryfabrics.com/wp-content/uploads/2020/01/storm.jpg",
            ),
            _fancybox(
                "PES900 Monet",
                "https://liveartgalleryfabrics.com/wp-content/uploads/2020/01/monet.jpg",
            ),
        ]
    )
    monkeypatch.setattr(art_gallery_fabrics, "_http_get", lambda _url: html)

    discovered = art_gallery_fabrics.discover(_config())

    assert [d.sku for d in discovered] == ["PE-594", "PES900"]
    assert all(d.product_url == CATALOG_URL for d in discovered)
    assert discovered[0].image_url.endswith("/storm.jpg")
    assert discovered[1].image_url.endswith("/monet.jpg")


def test_discover_raises_when_catalog_empty(monkeypatch):
    monkeypatch.setattr(
        art_gallery_fabrics, "_http_get", lambda _url: b"<html><body></body></html>"
    )
    with pytest.raises(art_gallery_fabrics.ParseError, match="no Pure Solids gallery entries"):
        art_gallery_fabrics.discover(_config())


def test_parse_returns_name_for_matching_sku():
    html = _catalog_html([_fancybox("PE-594 Storm")])
    parsed = art_gallery_fabrics.parse(html, _fetched("PE-594"), _config())
    assert parsed.sku == "PE-594"
    assert parsed.name == "Storm"
    assert parsed.product_url == CATALOG_URL


def test_parse_raises_when_sku_not_in_catalog():
    html = _catalog_html([_fancybox("PE-594 Storm")])
    with pytest.raises(art_gallery_fabrics.ParseError, match="no matching title found"):
        art_gallery_fabrics.parse(html, _fetched("PES999"), _config())
