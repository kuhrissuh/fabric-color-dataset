from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Optional

import merge
from models import (
    AlgorithmicResult,
    ExtractionResult,
    Line,
    LineConfig,
    Manufacturer,
    ParsedColor,
    VisionResult,
)

TODAY = date(2026, 4, 19)
PRIOR_DAY = date(2026, 4, 12)
FIRST_SEEN = date(2026, 3, 1)
SHA_A = "a" * 64
SHA_B = "b" * 64


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
        product_url_template="https://example.com/{sku}",
        image_url_template="https://example.com/{sku}.jpg",
        skus=[],
    )


def _extraction(
    sku: str = "K001-197",
    name: str = "Aloe",
    hex_: str = "#7ED3B0",
    algorithmic_hex: Optional[str] = None,
    image_sha: str = SHA_A,
    method: str = "vision_consensus",
    confidence: str = "high",
) -> ExtractionResult:
    parsed = ParsedColor(
        sku=sku,
        name=name,
        product_url=f"https://example.com/{sku}",
        image_url=f"https://example.com/{sku}.jpg",
        image_path=Path(f"/tmp/{sku}.jpg"),
        image_sha256=image_sha,
        fetched_on=TODAY,
    )
    return ExtractionResult(
        parsed=parsed,
        algorithmic=AlgorithmicResult(hex=algorithmic_hex or hex_, std_dev=1.0, std_a=0.0, std_b=0.0),
        classification="photograph",
        vision=VisionResult(hex=hex_, confidence=confidence, observations="", warnings=[]),
        delta_e=0.5,
        final_hex=hex_,
        final_method=method,
        final_confidence=confidence,
    )


def _prior_color(
    *,
    sku: str = "K001-197",
    name: str = "Aloe",
    hex_: str = "#7ED3B0",
    algorithmic_hex: Optional[str] = None,
    image_sha: str = SHA_A,
    method: str = "vision_consensus",
    confidence: str = "high",
    aliases: Optional[list] = None,
    status: str = "active",
    first_seen: date = FIRST_SEEN,
    source_collected_on: date = PRIOR_DAY,
) -> dict:
    return {
        "id": f"robert-kaufman-kona-cotton-{sku.lower()}",
        "name": name,
        "sku": sku,
        "aliases": list(aliases or []),
        "hex": hex_,
        "hex_method": method,
        "hex_confidence": confidence,
        "hex_algorithmic": algorithmic_hex or hex_,
        "hex_source": {
            "image_url": f"https://example.com/{sku}.jpg",
            "image_sha256": image_sha,
        },
        "manufacturer_product_url": f"https://example.com/{sku}",
        "status": status,
        "first_seen": first_seen.isoformat(),
        "source_collected_on": source_collected_on.isoformat(),
    }


def _write_prior(tmp_path: Path, colors: list[dict]) -> Path:
    path = tmp_path / "kona-cotton.json"
    path.write_text(json.dumps({"colors": colors}))
    return path


def test_new_color_initializes_dates_and_lands_in_added(tmp_path):
    path = tmp_path / "missing.json"  # never written
    records, diff = merge.merge([_extraction()], _config(), path, TODAY)

    assert len(records) == 1
    rec = records[0]
    assert rec.id == "robert-kaufman-kona-cotton-k001-197"
    assert rec.first_seen == TODAY
    assert rec.source_collected_on == TODAY
    assert rec.aliases == []
    assert rec.status == "active"
    assert diff.added == [rec.id]
    assert diff.hex_changed == []


def test_unchanged_color_holds_source_collected_on_steady(tmp_path):
    prior = _prior_color()
    path = _write_prior(tmp_path, [prior])

    records, diff = merge.merge([_extraction()], _config(), path, TODAY)

    assert len(records) == 1
    rec = records[0]
    assert rec.first_seen == FIRST_SEEN
    assert rec.source_collected_on == PRIOR_DAY
    assert diff.added == []
    assert diff.hex_changed == []
    assert diff.low_confidence == []
    assert diff.discontinued == []


def test_hex_change_bumps_source_collected_and_records_diff(tmp_path):
    prior = _prior_color(hex_="#111111", algorithmic_hex="#111111")
    path = _write_prior(tmp_path, [prior])

    records, diff = merge.merge([_extraction(hex_="#7ED3B0")], _config(), path, TODAY)

    rec = records[0]
    assert rec.hex == "#7ED3B0"
    assert rec.first_seen == FIRST_SEEN
    assert rec.source_collected_on == TODAY
    assert diff.hex_changed == [rec.id]


def test_manual_override_survives_when_image_sha_unchanged(tmp_path):
    prior = _prior_color(
        hex_="#FF0000",
        method="manual_override",
        confidence="high",
        image_sha=SHA_A,
    )
    path = _write_prior(tmp_path, [prior])

    extraction = _extraction(
        hex_="#7ED3B0",
        method="vision_consensus",
        confidence="medium",
        image_sha=SHA_A,
    )
    records, diff = merge.merge([extraction], _config(), path, TODAY)

    rec = records[0]
    assert rec.hex == "#FF0000"
    assert rec.hex_method == "manual_override"
    assert rec.hex_confidence == "high"
    assert diff.hex_changed == []


def test_manual_override_dropped_when_image_sha_changes(tmp_path):
    prior = _prior_color(
        hex_="#FF0000",
        method="manual_override",
        confidence="high",
        image_sha=SHA_A,
    )
    path = _write_prior(tmp_path, [prior])

    extraction = _extraction(
        hex_="#7ED3B0",
        method="vision_consensus",
        confidence="high",
        image_sha=SHA_B,
    )
    records, diff = merge.merge([extraction], _config(), path, TODAY)

    rec = records[0]
    assert rec.hex == "#7ED3B0"
    assert rec.hex_method == "vision_consensus"
    assert rec.image_sha256 == SHA_B
    assert rec.source_collected_on == TODAY
    assert diff.hex_changed == [rec.id]


def test_prior_color_absent_from_discovery_is_carried_through(tmp_path):
    leftover = _prior_color(sku="K001-999", name="Ghost", hex_="#222222")
    discovered = _prior_color(sku="K001-197")
    path = _write_prior(tmp_path, [leftover, discovered])

    records, diff = merge.merge([_extraction(sku="K001-197")], _config(), path, TODAY)

    by_sku = {r.sku: r for r in records}
    assert "K001-999" in by_sku
    ghost = by_sku["K001-999"]
    assert ghost.status == "active"
    assert ghost.first_seen == FIRST_SEEN
    assert ghost.source_collected_on == PRIOR_DAY
    assert diff.discontinued == []


def test_low_confidence_lands_in_low_confidence_diff(tmp_path):
    new = _extraction(sku="K001-1", confidence="low")
    existing = _extraction(sku="K001-2", confidence="low")
    prior = _prior_color(sku="K001-2", confidence="low")
    path = _write_prior(tmp_path, [prior])

    _, diff = merge.merge([new, existing], _config(), path, TODAY)

    assert sorted(diff.low_confidence) == sorted(
        [
            "robert-kaufman-kona-cotton-k001-1",
            "robert-kaufman-kona-cotton-k001-2",
        ]
    )


def test_aliases_preserved_across_merge(tmp_path):
    prior = _prior_color(aliases=["Avocado", "Old Aloe"])
    path = _write_prior(tmp_path, [prior])

    records, _ = merge.merge([_extraction()], _config(), path, TODAY)

    assert records[0].aliases == ["Avocado", "Old Aloe"]
