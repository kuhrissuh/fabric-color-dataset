from __future__ import annotations

import pytest

import fetch
from models import (
    DiscoveredColor,
    Line,
    LineConfig,
    Manufacturer,
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
        product_url_template="https://example.com/{sku}/",
        image_url_template="https://example.com/{sku}.jpg",
        skus=[],
    )


def _discovered(sku: str) -> DiscoveredColor:
    return DiscoveredColor(
        sku=sku,
        product_url=f"https://example.com/{sku}/",
        image_url=f"https://example.com/{sku}.jpg",
    )


def test_url_slug_keeps_per_sku_filename():
    # Kona per-SKU URL — last path segment is the SKU.
    assert (
        fetch._url_slug("https://www.robertkaufman.com/fabrics/kona_cotton/K001-197/")
        == "K001-197"
    )


def test_url_slug_collapses_shared_catalog_url():
    # AGF's single catalog URL — every SKU shares this page.
    assert (
        fetch._url_slug("https://liveartgalleryfabrics.com/pure-solids-quilting-cotton/")
        == "pure-solids-quilting-cotton"
    )


def test_url_slug_prepends_parent_for_numeric_tail():
    # Paginated catalog — naked "2" would be ambiguous, so parent segment
    # is prepended.
    assert (
        fetch._url_slug(
            "https://liveartgalleryfabrics.com/pure-solids-quilting-cotton/page/2/"
        )
        == "page-2"
    )


def test_url_slug_different_urls_produce_different_slugs():
    a = fetch._url_slug("https://example.com/catalog/page/2/")
    b = fetch._url_slug("https://example.com/catalog/page/3/")
    assert a != b


def test_url_slug_falls_back_to_hash_for_empty_path():
    # Root URL has no usable path — deterministic hash fallback.
    slug = fetch._url_slug("https://example.com/")
    assert len(slug) == 16
    assert slug == fetch._url_slug("https://example.com/")


def test_url_slug_strips_unsafe_characters():
    # Path segments with non-filename-safe characters are sanitized.
    slug = fetch._url_slug("https://example.com/a%20b/c+d/")
    assert "/" not in slug
    assert " " not in slug
    assert slug


def _install_stub_get(monkeypatch, responses):
    """responses: dict[url, bytes | Exception]. Missing URLs return b'OK'."""
    def fake_get(_session, url):
        resp = responses.get(url, b"OK")
        if isinstance(resp, Exception):
            raise resp
        return resp
    monkeypatch.setattr(fetch, "_get", fake_get)


def test_fetch_skips_sku_on_html_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(fetch, "RAW_DIR", tmp_path)
    _install_stub_get(monkeypatch, {
        "https://example.com/K001-002/": fetch.FetchError("boom"),
    })

    result = fetch.fetch(
        _config(),
        [_discovered("K001-001"), _discovered("K001-002"), _discovered("K001-003")],
    )

    assert [f.sku for f in result.fetched] == ["K001-001", "K001-003"]
    assert len(result.failures) == 1
    failure = result.failures[0]
    assert failure.sku == "K001-002"
    assert failure.kind == "html"
    assert failure.url == "https://example.com/K001-002/"
    assert "boom" in failure.error


def test_fetch_skips_sku_on_image_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(fetch, "RAW_DIR", tmp_path)
    _install_stub_get(monkeypatch, {
        "https://example.com/K001-002.jpg": fetch.FetchError("403"),
    })

    result = fetch.fetch(
        _config(),
        [_discovered("K001-001"), _discovered("K001-002"), _discovered("K001-003")],
    )

    assert [f.sku for f in result.fetched] == ["K001-001", "K001-003"]
    assert len(result.failures) == 1
    failure = result.failures[0]
    assert failure.sku == "K001-002"
    assert failure.kind == "image"
    assert failure.url == "https://example.com/K001-002.jpg"


def test_fetch_all_success_has_no_failures(monkeypatch, tmp_path):
    monkeypatch.setattr(fetch, "RAW_DIR", tmp_path)
    _install_stub_get(monkeypatch, {})

    result = fetch.fetch(
        _config(),
        [_discovered("K001-001"), _discovered("K001-002")],
    )

    assert len(result.fetched) == 2
    assert result.failures == []


def test_fetch_all_failures_returns_empty_fetched(monkeypatch, tmp_path):
    monkeypatch.setattr(fetch, "RAW_DIR", tmp_path)
    _install_stub_get(monkeypatch, {
        "https://example.com/K001-001/": fetch.FetchError("x"),
        "https://example.com/K001-002/": fetch.FetchError("x"),
    })

    result = fetch.fetch(
        _config(),
        [_discovered("K001-001"), _discovered("K001-002")],
    )

    assert result.fetched == []
    assert [f.sku for f in result.failures] == ["K001-001", "K001-002"]


def test_get_raises_fetch_error_after_retries(monkeypatch):
    import requests

    calls = {"n": 0}

    class _FakeResponse:
        def raise_for_status(self):
            raise requests.HTTPError("403")

    class _FakeSession:
        def get(self, *_args, **_kwargs):
            calls["n"] += 1
            return _FakeResponse()

    monkeypatch.setattr(fetch.time, "sleep", lambda _s: None)

    with pytest.raises(fetch.FetchError):
        fetch._get(_FakeSession(), "https://example.com/x")
    assert calls["n"] == fetch.RETRIES + 1
