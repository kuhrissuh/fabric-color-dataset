from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from models import FetchedColor, Line, LineConfig, Manufacturer
from scrapers import riley_blake_designs

API_URL = (
    "https://www.rileyblakedesigns.com/api/cacheable/items"
    "?c=4582045&commercecategoryurl=%2FFabric%2FBasics%2FConfetti-Cottons"
    "&country=US&currency=USD&fieldset=search&language=en"
    "&limit=100&offset=0&use_pcv=T"
)


def _config(product_url: str = API_URL) -> LineConfig:
    return LineConfig(
        manufacturer=Manufacturer(
            name="Riley Blake Designs",
            slug="riley-blake-designs",
            website="https://www.rileyblakedesigns.com",
        ),
        line=Line(
            name="Confetti Cottons",
            slug="confetti-cottons",
            substrate="cotton",
            weight_oz_per_sq_yd=4.1,
            width_inches=44.0,
        ),
        notes="",
        id_scheme="manufacturer_sku",
        scraper="riley_blake_designs",
        product_url_template=product_url,
        image_url_template=None,
        skus=[],
    )


def _item(
    itemid: str,
    name: str = "",
    urlcomponent: str = "",
) -> dict:
    return {
        "itemid": itemid,
        "storedisplayname": name or f"Confetti Cotton\u2122 {itemid}",
        "urlcomponent": urlcomponent or f"Confetti-Cotton-{itemid}",
    }


def _payload(items: list[dict], total: int | None = None) -> bytes:
    return json.dumps(
        {"total": total if total is not None else len(items), "items": items}
    ).encode()


def _fetched(sku: str = "C120-ZUCCHINI") -> FetchedColor:
    return FetchedColor(
        sku=sku,
        product_url=API_URL,
        image_url=f"https://example.com/{sku}_media-1.jpg",
        html_path=Path(f"/tmp/{sku}.html"),
        image_path=Path(f"/tmp/{sku}.jpg"),
        image_sha256="a" * 64,
        fetched_on=date(2026, 4, 19),
    )


def test_discover_filters_to_base_color_skus(monkeypatch):
    # Category includes base colors plus precuts, bolts, swatch cards — only
    # the base colors (^C120-[A-Z0-9]+$) should come through.
    items = [
        _item("SW120-2SM", "Confetti Cotton\u2122 Swatch Card Small"),
        _item("C120-RILEYBLACK-20", "Confetti Cotton\u2122 Riley Black 20 Yards"),
        _item("RP120-ZUCCHINI", "Confetti Cotton\u2122 Zucchini Roll Up"),
        _item("C120-ZUCCHINI", "Confetti Cotton\u2122 Zucchini", "Confetti-Cotton-Zucchini"),
        _item("C120-ALPINE", "Confetti Cotton\u2122 Alpine", "Confetti-Cotton-Alpine"),
    ]
    monkeypatch.setattr(
        riley_blake_designs, "_http_get", lambda _url: _payload(items)
    )

    discovered = riley_blake_designs.discover(_config())

    assert [d.sku for d in discovered] == ["C120-ZUCCHINI", "C120-ALPINE"]


def test_discover_builds_image_url_from_itemid_with_encoded_space(monkeypatch):
    items = [_item("C120-ZUCCHINI")]
    monkeypatch.setattr(
        riley_blake_designs, "_http_get", lambda _url: _payload(items)
    )

    discovered = riley_blake_designs.discover(_config())

    assert discovered[0].image_url == (
        "https://www.rileyblakedesigns.com/assets/Product%20Images/"
        "C120-ZUCCHINI_media-1.jpg"
    )


def test_discover_paginates_until_offset_covers_total(monkeypatch):
    # Shrink _PAGE_SIZE so pagination is exercised with small fixtures; in
    # production the server caps it at 100.
    monkeypatch.setattr(riley_blake_designs, "_PAGE_SIZE", 2)
    page_one = _payload(
        [_item("C120-A"), _item("C120-B")], total=3
    )
    page_two = _payload([_item("C120-C")], total=3)

    def responder(url: str) -> bytes:
        if "offset=0" in url:
            return page_one
        if "offset=2" in url:
            return page_two
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(riley_blake_designs, "_http_get", responder)

    discovered = riley_blake_designs.discover(_config())

    assert [d.sku for d in discovered] == ["C120-A", "C120-B", "C120-C"]
    assert "offset=0" in discovered[0].product_url
    assert "offset=2" in discovered[2].product_url


def test_discover_dedupes_skus_across_pages(monkeypatch):
    monkeypatch.setattr(riley_blake_designs, "_PAGE_SIZE", 1)
    page_one = _payload([_item("C120-A")], total=2)
    page_two = _payload([_item("C120-A"), _item("C120-B")], total=2)

    def responder(url: str) -> bytes:
        return page_one if "offset=0" in url else page_two

    monkeypatch.setattr(riley_blake_designs, "_http_get", responder)

    discovered = riley_blake_designs.discover(_config())

    assert [d.sku for d in discovered] == ["C120-A", "C120-B"]
    # First occurrence wins — C120-A keeps the offset=0 URL.
    assert "offset=0" in discovered[0].product_url


def test_discover_raises_when_total_is_zero(monkeypatch):
    monkeypatch.setattr(
        riley_blake_designs,
        "_http_get",
        lambda _url: _payload([], total=0),
    )
    with pytest.raises(
        riley_blake_designs.ParseError, match="no Confetti Cottons items"
    ):
        riley_blake_designs.discover(_config())


def test_discover_rejects_template_without_offset_placeholder():
    bad_config = _config(product_url="https://example.com/api?limit=100")
    with pytest.raises(
        riley_blake_designs.ParseError, match="must contain `offset=0`"
    ):
        riley_blake_designs.discover(bad_config)


def test_parse_strips_trademark_prefix_and_uses_urlcomponent():
    body = _payload(
        [
            _item(
                "C120-ZUCCHINI",
                name="Confetti Cotton\u2122 Zucchini",
                urlcomponent="Confetti-Cotton-Zucchini",
            )
        ]
    )
    parsed = riley_blake_designs.parse(body, _fetched("C120-ZUCCHINI"), _config())

    assert parsed.name == "Zucchini"
    assert (
        parsed.product_url
        == "https://www.rileyblakedesigns.com/Confetti-Cotton-Zucchini"
    )


def test_parse_handles_prefix_without_trademark_glyph():
    body = _payload(
        [
            _item(
                "C120-STORM",
                name="Confetti Cotton Storm",
                urlcomponent="Confetti-Cotton-Storm",
            )
        ]
    )
    parsed = riley_blake_designs.parse(body, _fetched("C120-STORM"), _config())
    assert parsed.name == "Storm"


def test_parse_preserves_multiword_names():
    body = _payload(
        [
            _item(
                "C120-BEARLAKE",
                name="Confetti Cotton\u2122 Bear Lake",
                urlcomponent="Confetti-Cotton-Bear-Lake",
            )
        ]
    )
    parsed = riley_blake_designs.parse(body, _fetched("C120-BEARLAKE"), _config())
    assert parsed.name == "Bear Lake"


def test_parse_raises_when_sku_not_in_payload():
    body = _payload([_item("C120-ZUCCHINI")])
    with pytest.raises(
        riley_blake_designs.ParseError, match="not present in fetched JSON batch"
    ):
        riley_blake_designs.parse(body, _fetched("C120-MISSING"), _config())


def test_parse_raises_on_missing_urlcomponent():
    body = _payload(
        [{"itemid": "C120-ZUCCHINI", "storedisplayname": "Confetti Cotton\u2122 Zucchini", "urlcomponent": ""}]
    )
    with pytest.raises(
        riley_blake_designs.ParseError, match="missing urlcomponent"
    ):
        riley_blake_designs.parse(body, _fetched("C120-ZUCCHINI"), _config())


def test_parse_raises_on_unparseable_name():
    body = _payload(
        [
            {
                "itemid": "C120-ZUCCHINI",
                "storedisplayname": "Confetti Cotton\u2122 ",
                "urlcomponent": "Confetti-Cotton-Zucchini",
            }
        ]
    )
    with pytest.raises(
        riley_blake_designs.ParseError, match="could not extract color name"
    ):
        riley_blake_designs.parse(body, _fetched("C120-ZUCCHINI"), _config())


def test_parse_raises_on_malformed_json():
    with pytest.raises(
        riley_blake_designs.ParseError, match="could not decode"
    ):
        riley_blake_designs.parse(b"{not json", _fetched(), _config())
