from __future__ import annotations

import copy
from typing import Any

import jsonschema
import pytest

import validate

VALID: dict[str, Any] = {
    "schema_version": "1.0.0",
    "data_version": "0.1.0",
    "manufacturer": {
        "name": "Art Gallery Fabrics",
        "slug": "art-gallery-fabrics",
        "website": "https://www.artgalleryfabrics.com",
    },
    "line": {
        "name": "Pure Solids",
        "slug": "pure-solids",
        "substrate": "cotton",
        "weight_oz_per_sq_yd": 4.4,
        "width_inches": 44,
    },
    "notes": "Core solids line.",
    "id_scheme": "manufacturer_sku",
    "generated_on": "2026-04-17",
    "generator_version": "0.1.0",
    "color_count": 1,
    "colors": [
        {
            "id": "art-gallery-fabrics-pure-solids-pe-404",
            "name": "Caramel",
            "sku": "PE-404",
            "aliases": [],
            "hex": "#8B4513",
            "hex_method": "vision_consensus",
            "hex_confidence": "high",
            "hex_algorithmic": "#8A4412",
            "hex_source": {
                "image_url": "https://example.com/pe-404.jpg",
                "image_sha256": "a" * 64,
            },
            "manufacturer_product_url": "https://example.com/pe-404",
            "status": "active",
            "first_seen": "2026-04-17",
            "source_collected_on": "2026-04-17",
        }
    ],
}


def fresh() -> dict[str, Any]:
    return copy.deepcopy(VALID)


def test_valid_passes():
    validate.validate(fresh())


def test_slugify_handles_spaces_and_punctuation():
    assert validate.slugify("PE-404") == "pe-404"
    assert validate.slugify("PE 404") == "pe-404"
    assert validate.slugify("PE/404") == "pe-404"
    assert validate.slugify("  PE---404  ") == "pe-404"


def test_color_count_mismatch():
    data = fresh()
    data["color_count"] = 2
    with pytest.raises(validate.ValidationError, match="color_count"):
        validate.validate(data)


def test_id_does_not_match_slugs():
    data = fresh()
    data["colors"][0]["id"] = "art-gallery-fabrics-pure-solids-wrong"
    with pytest.raises(validate.ValidationError, match="expected"):
        validate.validate(data)


def test_id_derives_from_slugified_sku():
    data = fresh()
    data["colors"][0]["sku"] = "PE 404"
    validate.validate(data)


def test_duplicate_ids():
    data = fresh()
    data["colors"].append(copy.deepcopy(data["colors"][0]))
    data["color_count"] = 2
    with pytest.raises(validate.ValidationError, match="duplicate"):
        validate.validate(data)


def test_first_seen_after_source_collected():
    data = fresh()
    data["colors"][0]["first_seen"] = "2026-05-01"
    data["colors"][0]["source_collected_on"] = "2026-04-17"
    with pytest.raises(validate.ValidationError, match="first_seen"):
        validate.validate(data)


def test_source_collected_after_generated():
    data = fresh()
    data["colors"][0]["source_collected_on"] = "2026-04-18"
    with pytest.raises(validate.ValidationError, match="source_collected_on"):
        validate.validate(data)


def test_lowercase_hex_rejected():
    data = fresh()
    data["colors"][0]["hex"] = "#8b4513"
    with pytest.raises(jsonschema.ValidationError):
        validate.validate(data)


def test_unknown_status_rejected():
    data = fresh()
    data["colors"][0]["status"] = "retired"
    with pytest.raises(jsonschema.ValidationError):
        validate.validate(data)


def test_extra_top_level_property_rejected():
    data = fresh()
    data["unexpected"] = True
    with pytest.raises(jsonschema.ValidationError):
        validate.validate(data)


def test_extra_color_property_rejected():
    data = fresh()
    data["colors"][0]["extra"] = "nope"
    with pytest.raises(jsonschema.ValidationError):
        validate.validate(data)


def test_bad_sha256_length():
    data = fresh()
    data["colors"][0]["hex_source"]["image_sha256"] = "a" * 63
    with pytest.raises(jsonschema.ValidationError):
        validate.validate(data)


def test_timestamp_in_date_field_rejected():
    data = fresh()
    data["generated_on"] = "2026-04-17T12:00:00Z"
    with pytest.raises(jsonschema.ValidationError):
        validate.validate(data)


def test_uppercase_slug_rejected():
    data = fresh()
    data["manufacturer"]["slug"] = "Art-Gallery-Fabrics"
    with pytest.raises(jsonschema.ValidationError):
        validate.validate(data)


def test_non_https_url_rejected():
    data = fresh()
    data["manufacturer"]["website"] = "ftp://example.com"
    with pytest.raises(jsonschema.ValidationError):
        validate.validate(data)
