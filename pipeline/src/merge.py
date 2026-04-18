"""Combine fresh extractions with any existing data file.

Responsibilities:
- Preserve stable IDs and the original `first_seen` date.
- Preserve `aliases` across runs.
- Honor `hex_method: "manual_override"` from prior runs unless the source
  image hash has changed (per docs/project-plan.md).
- Only bump `source_collected_on` when something actually changed for that
  color; otherwise hold the prior date steady.
- Emit a LineDiff describing what changed for the PR summary / changelog.

For v0.1 calibration we only discover the configured SKU list; any colors
absent from that list and present in the prior file are left untouched.
Status transitions (active -> discontinued when a URL 404s) are deferred
until step 5 runs against the full catalog.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from models import ColorRecord, ExtractionResult, LineConfig, LineDiff
from validate import slugify


def merge(
    extractions: List[ExtractionResult],
    config: LineConfig,
    existing_path: Path,
    today: date,
) -> Tuple[List[ColorRecord], LineDiff]:
    prior = _load_prior(existing_path)
    prior_by_id = {c["id"]: c for c in prior.get("colors", [])}

    records: List[ColorRecord] = []
    diff = LineDiff()

    for ex in extractions:
        record_id = _build_id(config, ex.parsed.sku)
        prior_color = prior_by_id.pop(record_id, None)

        if prior_color is None:
            diff.added.append(record_id)
            records.append(_from_fresh(record_id, ex, today))
            continue

        merged = _merge_one(record_id, ex, prior_color, today, diff)
        records.append(merged)

    # Any colors that stayed in prior_by_id were not in today's discovery
    # set. For the calibration run we carry them through unchanged.
    for leftover in prior_by_id.values():
        records.append(_from_prior_dict(leftover))

    records.sort(key=lambda r: r.sku)

    for ex in extractions:
        if ex.final_confidence == "low":
            diff.low_confidence.append(_build_id(config, ex.parsed.sku))

    return records, diff


def _build_id(config: LineConfig, sku: str) -> str:
    return (
        f"{config.manufacturer.slug}-{config.line.slug}-{slugify(sku)}"
    )


def _from_fresh(
    record_id: str, ex: ExtractionResult, today: date
) -> ColorRecord:
    return ColorRecord(
        id=record_id,
        name=ex.parsed.name,
        sku=ex.parsed.sku,
        aliases=[],
        hex=ex.final_hex,
        hex_method=ex.final_method,
        hex_confidence=ex.final_confidence,
        hex_algorithmic=ex.algorithmic.hex,
        image_url=ex.parsed.image_url,
        image_sha256=ex.parsed.image_sha256,
        manufacturer_product_url=ex.parsed.product_url,
        status="active",
        first_seen=today,
        source_collected_on=today,
    )


def _merge_one(
    record_id: str,
    ex: ExtractionResult,
    prior: dict,
    today: date,
    diff: LineDiff,
) -> ColorRecord:
    first_seen = date.fromisoformat(prior["first_seen"])
    prior_image_sha = prior["hex_source"]["image_sha256"]
    prior_method = prior["hex_method"]

    # Manual overrides win until the source image changes.
    if (
        prior_method == "manual_override"
        and prior_image_sha == ex.parsed.image_sha256
    ):
        hex_value = prior["hex"]
        hex_method = prior_method
        hex_confidence = prior["hex_confidence"]
    else:
        hex_value = ex.final_hex
        hex_method = ex.final_method
        hex_confidence = ex.final_confidence

    something_changed = (
        prior["hex"] != hex_value
        or prior_image_sha != ex.parsed.image_sha256
        or prior["name"] != ex.parsed.name
        or prior["hex_method"] != hex_method
        or prior["hex_confidence"] != hex_confidence
        or prior["hex_algorithmic"] != ex.algorithmic.hex
        or prior["manufacturer_product_url"] != ex.parsed.product_url
    )
    source_collected_on = (
        today if something_changed
        else date.fromisoformat(prior["source_collected_on"])
    )

    if prior["hex"] != hex_value:
        diff.hex_changed.append(record_id)

    return ColorRecord(
        id=record_id,
        name=ex.parsed.name,
        sku=ex.parsed.sku,
        aliases=list(prior.get("aliases", [])),
        hex=hex_value,
        hex_method=hex_method,
        hex_confidence=hex_confidence,
        hex_algorithmic=ex.algorithmic.hex,
        image_url=ex.parsed.image_url,
        image_sha256=ex.parsed.image_sha256,
        manufacturer_product_url=ex.parsed.product_url,
        status=prior.get("status", "active"),
        first_seen=first_seen,
        source_collected_on=source_collected_on,
    )


def _from_prior_dict(prior: dict) -> ColorRecord:
    return ColorRecord(
        id=prior["id"],
        name=prior["name"],
        sku=prior["sku"],
        aliases=list(prior.get("aliases", [])),
        hex=prior["hex"],
        hex_method=prior["hex_method"],
        hex_confidence=prior["hex_confidence"],
        hex_algorithmic=prior["hex_algorithmic"],
        image_url=prior["hex_source"]["image_url"],
        image_sha256=prior["hex_source"]["image_sha256"],
        manufacturer_product_url=prior["manufacturer_product_url"],
        status=prior["status"],
        first_seen=date.fromisoformat(prior["first_seen"]),
        source_collected_on=date.fromisoformat(prior["source_collected_on"]),
    )


def _load_prior(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open() as f:
        return json.load(f)
