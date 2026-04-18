"""Typed data carriers for stage boundaries.

Every pipeline stage consumes and produces instances of these dataclasses;
no dicts cross stage boundaries. Changing a field here causes the type
checker to identify every stage that needs to update.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import List, Optional


@dataclass(frozen=True)
class Manufacturer:
    name: str
    slug: str
    website: str


@dataclass(frozen=True)
class Line:
    name: str
    slug: str
    substrate: str
    weight_oz_per_sq_yd: float
    width_inches: float


@dataclass(frozen=True)
class LineConfig:
    manufacturer: Manufacturer
    line: Line
    notes: str
    id_scheme: str
    scraper: str
    product_url_template: str
    image_url_template: str
    skus: List[str]


@dataclass(frozen=True)
class DiscoveredColor:
    sku: str
    product_url: str
    image_url: str


@dataclass(frozen=True)
class FetchedColor:
    sku: str
    product_url: str
    image_url: str
    html_path: Path
    image_path: Path
    image_sha256: str
    fetched_on: date


@dataclass(frozen=True)
class ParsedColor:
    sku: str
    name: str
    product_url: str
    image_url: str
    image_path: Path
    image_sha256: str
    fetched_on: date


@dataclass(frozen=True)
class AlgorithmicResult:
    hex: str
    std_dev: float


@dataclass(frozen=True)
class VisionResult:
    hex: str
    confidence: str
    observations: str
    warnings: List[str]


@dataclass(frozen=True)
class ExtractionResult:
    parsed: ParsedColor
    algorithmic: AlgorithmicResult
    vision: VisionResult
    delta_e: float
    final_hex: str
    final_method: str
    final_confidence: str


@dataclass(frozen=True)
class ColorRecord:
    """Mirrors one entry in the `colors` array of the output JSON."""
    id: str
    name: str
    sku: str
    aliases: List[str]
    hex: str
    hex_method: str
    hex_confidence: str
    hex_algorithmic: str
    image_url: str
    image_sha256: str
    manufacturer_product_url: str
    status: str
    first_seen: date
    source_collected_on: date

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "sku": self.sku,
            "aliases": list(self.aliases),
            "hex": self.hex,
            "hex_method": self.hex_method,
            "hex_confidence": self.hex_confidence,
            "hex_algorithmic": self.hex_algorithmic,
            "hex_source": {
                "image_url": self.image_url,
                "image_sha256": self.image_sha256,
            },
            "manufacturer_product_url": self.manufacturer_product_url,
            "status": self.status,
            "first_seen": self.first_seen.isoformat(),
            "source_collected_on": self.source_collected_on.isoformat(),
        }


@dataclass(frozen=True)
class LineDiff:
    added: List[str] = field(default_factory=list)
    discontinued: List[str] = field(default_factory=list)
    hex_changed: List[str] = field(default_factory=list)
    low_confidence: List[str] = field(default_factory=list)
