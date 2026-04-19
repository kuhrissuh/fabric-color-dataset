from __future__ import annotations

import json
from datetime import date

import cli
from models import ColorRecord, LineDiff


def _record(cid: str, name: str, sku: str, hex_: str) -> ColorRecord:
    return ColorRecord(
        id=cid,
        name=name,
        sku=sku,
        aliases=[],
        hex=hex_,
        hex_method="vision_consensus",
        hex_confidence="high",
        hex_algorithmic=hex_,
        image_url="https://example.com/img.jpg",
        image_sha256="a" * 64,
        manufacturer_product_url="https://example.com/p",
        status="active",
        first_seen=date(2026, 4, 17),
        source_collected_on=date(2026, 4, 18),
    )


def test_halt_fires_above_hex_change_threshold():
    diff = LineDiff(hex_changed=[f"id-{i}" for i in range(25)])
    reason = cli._check_halt(diff, processed_count=100)
    assert reason is not None
    assert "hex_change_rate" in reason


def test_halt_fires_above_low_confidence_threshold():
    diff = LineDiff(low_confidence=[f"id-{i}" for i in range(15)])
    reason = cli._check_halt(diff, processed_count=100)
    assert reason is not None
    assert "low_confidence_rate" in reason


def test_halt_silent_when_both_rates_within_bounds():
    diff = LineDiff(
        hex_changed=[f"id-{i}" for i in range(20)],
        low_confidence=[f"id-{i}" for i in range(10)],
    )
    # 20% and 10% exactly — thresholds are strict greater-than, so no halt.
    assert cli._check_halt(diff, processed_count=100) is None


def test_halt_handles_empty_run():
    assert cli._check_halt(LineDiff(), processed_count=0) is None


def test_summary_json_captures_before_after_hex(tmp_path):
    records = [
        _record("m-l-a", "Alpha", "K001-1", "#112233"),
        _record("m-l-b", "Beta", "K001-2", "#445566"),
    ]
    prior_colors = {
        "m-l-a": {"id": "m-l-a", "name": "Alpha", "sku": "K001-1", "hex": "#111111"},
    }
    diff = LineDiff(added=["m-l-b"], hex_changed=["m-l-a"])

    out = tmp_path / "summary.json"
    cli._write_summary(
        out,
        line_path="m/l",
        prior_version="0.1.0",
        new_version="0.1.1",
        diff=diff,
        records=records,
        prior_colors_by_id=prior_colors,
        halt_reason=None,
    )

    payload = json.loads(out.read_text())
    assert payload["halt"] is None
    assert payload["changed"] is True
    assert payload["new_data_version"] == "0.1.1"
    assert payload["counts"]["added"] == 1
    assert payload["counts"]["hex_changed"] == 1
    assert payload["added"] == [
        {"id": "m-l-b", "name": "Beta", "sku": "K001-2", "hex": "#445566"}
    ]
    assert payload["hex_changed"] == [
        {
            "id": "m-l-a",
            "name": "Alpha",
            "sku": "K001-1",
            "before": "#111111",
            "after": "#112233",
        }
    ]


def test_summary_json_records_halt(tmp_path):
    out = tmp_path / "summary.json"
    cli._write_summary(
        out,
        line_path="m/l",
        prior_version="0.1.0",
        new_version=None,
        diff=LineDiff(hex_changed=["x"] * 25),
        records=[],
        prior_colors_by_id={},
        halt_reason="hex_change_rate=25% exceeds 20%",
    )

    payload = json.loads(out.read_text())
    assert payload["halt"].startswith("hex_change_rate")
    assert payload["new_data_version"] is None
