from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

import validate
import write


def _line_doc(*, manufacturer_slug: str, manufacturer_name: str,
              line_slug: str, line_name: str, color_count: int,
              data_version: str) -> dict:
    return {
        "schema_version": "1.0.0",
        "data_version": data_version,
        "manufacturer": {
            "name": manufacturer_name,
            "slug": manufacturer_slug,
            "website": f"https://example.com/{manufacturer_slug}",
        },
        "line": {
            "name": line_name,
            "slug": line_slug,
            "substrate": "cotton",
            "weight_oz_per_sq_yd": 4.0,
            "width_inches": 44.0,
        },
        "notes": "",
        "id_scheme": "manufacturer_sku",
        "generated_on": "2026-04-19",
        "generator_version": "0.1.0",
        "color_count": color_count,
        "colors": [],
    }


def _seed(data_dir: Path, doc: dict) -> None:
    sub = data_dir / doc["manufacturer"]["slug"]
    sub.mkdir(parents=True, exist_ok=True)
    (sub / f"{doc['line']['slug']}.json").write_text(json.dumps(doc))


def test_write_index_emits_sorted_entries(tmp_path: Path) -> None:
    # Seed in reverse alphabetical order to prove the function sorts.
    _seed(tmp_path, _line_doc(
        manufacturer_slug="robert-kaufman",
        manufacturer_name="Robert Kaufman",
        line_slug="kona-cotton",
        line_name="Kona Cotton",
        color_count=370,
        data_version="0.2.0",
    ))
    _seed(tmp_path, _line_doc(
        manufacturer_slug="art-gallery-fabrics",
        manufacturer_name="Art Gallery Fabrics",
        line_slug="pure-solids",
        line_name="Pure Solids",
        color_count=215,
        data_version="0.2.0",
    ))

    out = write.write_index(date(2026, 4, 19), data_dir=tmp_path)

    assert out == tmp_path / "index.json"
    payload = json.loads(out.read_text())
    assert payload["schema_version"] == "1.0.0"
    assert payload["generated_on"] == "2026-04-19"
    assert [e["line_slug"] for e in payload["lines"]] == [
        "pure-solids", "kona-cotton",
    ]
    assert payload["lines"][0] == {
        "manufacturer_slug": "art-gallery-fabrics",
        "line_slug": "pure-solids",
        "path": "art-gallery-fabrics/pure-solids.json",
        "manufacturer_name": "Art Gallery Fabrics",
        "line_name": "Pure Solids",
        "color_count": 215,
        "data_version": "0.2.0",
    }


def test_write_index_passes_schema_validation(tmp_path: Path) -> None:
    _seed(tmp_path, _line_doc(
        manufacturer_slug="robert-kaufman",
        manufacturer_name="Robert Kaufman",
        line_slug="kona-cotton",
        line_name="Kona Cotton",
        color_count=370,
        data_version="0.2.0",
    ))

    out = write.write_index(date(2026, 4, 19), data_dir=tmp_path)
    validate.validate_index_file(out)


def test_write_index_empty_data_dir(tmp_path: Path) -> None:
    out = write.write_index(date(2026, 4, 19), data_dir=tmp_path)
    payload = json.loads(out.read_text())
    assert payload["lines"] == []
    validate.validate_index_file(out)


def test_write_index_ignores_top_level_index_json(tmp_path: Path) -> None:
    # Pre-existing top-level index.json should not be picked up as a line file.
    (tmp_path / "index.json").write_text("{}")
    _seed(tmp_path, _line_doc(
        manufacturer_slug="robert-kaufman",
        manufacturer_name="Robert Kaufman",
        line_slug="kona-cotton",
        line_name="Kona Cotton",
        color_count=370,
        data_version="0.2.0",
    ))

    out = write.write_index(date(2026, 4, 19), data_dir=tmp_path)
    payload = json.loads(out.read_text())
    assert len(payload["lines"]) == 1
    assert payload["lines"][0]["line_slug"] == "kona-cotton"
