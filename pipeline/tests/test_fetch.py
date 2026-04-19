from __future__ import annotations

import fetch


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
