"""Load a per-line YAML config into a typed LineConfig."""

from __future__ import annotations

from pathlib import Path

import yaml

from models import Line, LineConfig, Manufacturer

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIGS_DIR = REPO_ROOT / "configs"


def load(line_path: str) -> LineConfig:
    """Load configs/{line_path}.yaml. `line_path` is e.g. 'robert-kaufman/kona-cotton'."""
    path = CONFIGS_DIR / f"{line_path}.yaml"
    with path.open() as f:
        raw = yaml.safe_load(f)

    mfr = raw["manufacturer"]
    line = raw["line"]
    templates = raw["url_templates"]
    return LineConfig(
        manufacturer=Manufacturer(
            name=mfr["name"], slug=mfr["slug"], website=mfr["website"]
        ),
        line=Line(
            name=line["name"],
            slug=line["slug"],
            substrate=line["substrate"],
            weight_oz_per_sq_yd=float(line["weight_oz_per_sq_yd"]),
            width_inches=float(line["width_inches"]),
        ),
        notes=raw["notes"].strip(),
        id_scheme=raw["id_scheme"],
        scraper=raw["scraper"],
        product_url_template=templates["product"],
        image_url_template=templates["image"],
        skus=list(raw["skus"]),
    )
