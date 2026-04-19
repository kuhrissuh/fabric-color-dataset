from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from models import FetchedColor, Line, LineConfig, Manufacturer
from scrapers import robert_kaufman


def _fetched(sku: str = "K001-197") -> FetchedColor:
    return FetchedColor(
        sku=sku,
        product_url=f"https://example.com/{sku}",
        image_url=f"https://example.com/{sku}.jpg",
        html_path=Path(f"/tmp/{sku}.html"),
        image_path=Path(f"/tmp/{sku}.jpg"),
        image_sha256="a" * 64,
        fetched_on=date(2026, 4, 19),
    )


def _config() -> LineConfig:
    return LineConfig(
        manufacturer=Manufacturer(
            name="Robert Kaufman",
            slug="robert-kaufman",
            website="https://www.robertkaufman.com",
        ),
        line=Line(
            name="Kona Cotton",
            slug="kona-cotton",
            substrate="cotton",
            weight_oz_per_sq_yd=4.35,
            width_inches=44.0,
        ),
        notes="",
        id_scheme="manufacturer_sku",
        scraper="kona",
        product_url_template="",
        image_url_template="",
        skus=[],
    )


def _og_html(content: str) -> bytes:
    return f'<html><head><meta property="og:title" content="{content}"></head><body></body></html>'.encode()


def _h1_html(inner: str) -> bytes:
    return f'<html><body><h1 class="page_title">{inner}</h1></body></html>'.encode()


def test_og_title_parses_name():
    parsed = robert_kaufman.parse(
        _og_html("K001-197 ALOE  from Kona® Cotton"), _fetched(), _config()
    )
    assert parsed.name == "Aloe"
    assert parsed.sku == "K001-197"


def test_og_title_titlecases_uppercase_name():
    parsed = robert_kaufman.parse(
        _og_html("K001-1182 HONEY DEW from Kona® Cotton"),
        _fetched("K001-1182"),
        _config(),
    )
    assert parsed.name == "Honey Dew"


def test_og_title_collapses_whitespace_in_name():
    parsed = robert_kaufman.parse(
        _og_html("K001-197 ALOE   GREEN  from Kona® Cotton"), _fetched(), _config()
    )
    assert parsed.name == "Aloe Green"


def test_h1_fallback_when_og_title_missing():
    html = _h1_html('K001-197 ALOE from <a href="/kona">Kona® Cotton</a>')
    parsed = robert_kaufman.parse(html, _fetched(), _config())
    assert parsed.name == "Aloe"


def test_missing_title_raises():
    with pytest.raises(robert_kaufman.ParseError, match="neither og:title nor h1.page_title"):
        robert_kaufman.parse(b"<html><body>nope</body></html>", _fetched(), _config())


def test_malformed_title_raises():
    html = _h1_html("not a real product title")
    with pytest.raises(robert_kaufman.ParseError, match="did not match expected"):
        robert_kaufman.parse(html, _fetched(), _config())


def test_sku_mismatch_raises():
    html = _og_html("K001-200 OCEAN from Kona® Cotton")
    with pytest.raises(robert_kaufman.ParseError, match="site markup may have changed"):
        robert_kaufman.parse(html, _fetched("K001-197"), _config())
