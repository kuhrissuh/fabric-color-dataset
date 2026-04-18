"""Write the data JSON file and append a changelog entry.

Both the JSON and the changelog live under data/{manufacturer}/. The
changelog captures the *why* of each run (added/discontinued/hex updates);
git history captures the raw diff.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import List, Tuple

from models import ColorRecord, LineConfig, LineDiff

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"

SCHEMA_VERSION = "1.0.0"
GENERATOR_VERSION = "0.1.0"


def data_path(config: LineConfig) -> Path:
    return DATA_DIR / config.manufacturer.slug / f"{config.line.slug}.json"


def changelog_path(config: LineConfig) -> Path:
    return (
        DATA_DIR / config.manufacturer.slug
        / f"{config.line.slug}.changelog.md"
    )


def write(
    config: LineConfig,
    records: List[ColorRecord],
    diff: LineDiff,
    today: date,
    prior_data_version: str,
) -> Tuple[Path, str]:
    new_version = _bump_version(prior_data_version, diff)
    data_p = data_path(config)
    data_p.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "data_version": new_version,
        "manufacturer": {
            "name": config.manufacturer.name,
            "slug": config.manufacturer.slug,
            "website": config.manufacturer.website,
        },
        "line": {
            "name": config.line.name,
            "slug": config.line.slug,
            "substrate": config.line.substrate,
            "weight_oz_per_sq_yd": config.line.weight_oz_per_sq_yd,
            "width_inches": config.line.width_inches,
        },
        "notes": config.notes,
        "id_scheme": config.id_scheme,
        "generated_on": today.isoformat(),
        "generator_version": GENERATOR_VERSION,
        "color_count": len(records),
        "colors": [r.to_json() for r in records],
    }
    data_p.write_text(json.dumps(payload, indent=2) + "\n")

    _append_changelog(config, diff, today, new_version)
    return data_p, new_version


def load_prior_data_version(config: LineConfig) -> str:
    path = data_path(config)
    if not path.exists():
        return "0.0.0"
    with path.open() as f:
        return json.load(f).get("data_version", "0.0.0")


def _bump_version(prior: str, diff: LineDiff) -> str:
    major, minor, patch = (int(p) for p in prior.split("."))
    if diff.added or diff.discontinued:
        minor += 1
        patch = 0
    elif diff.hex_changed:
        patch += 1
    else:
        # First emission of an empty prior -> initial 0.1.0.
        if prior == "0.0.0":
            return "0.1.0"
    return f"{major}.{minor}.{patch}"


def _append_changelog(
    config: LineConfig, diff: LineDiff, today: date, version: str
) -> None:
    path = changelog_path(config)
    if not path.exists():
        path.write_text(
            f"# {config.line.name} changelog\n\n"
            "Per-run record of changes to this line's data file. The "
            "raw diff lives in git; this file captures the *why*.\n"
        )

    lines = [
        "",
        f"## {version} — {today.isoformat()}",
        "",
    ]
    if diff.added:
        lines.append(f"- Added {len(diff.added)} color(s): "
                     + ", ".join(f"`{i}`" for i in diff.added))
    if diff.discontinued:
        lines.append(f"- Discontinued {len(diff.discontinued)} color(s): "
                     + ", ".join(f"`{i}`" for i in diff.discontinued))
    if diff.hex_changed:
        lines.append(f"- Hex updated for {len(diff.hex_changed)} color(s): "
                     + ", ".join(f"`{i}`" for i in diff.hex_changed))
    if diff.low_confidence:
        lines.append(
            f"- {len(diff.low_confidence)} color(s) flagged low-confidence: "
            + ", ".join(f"`{i}`" for i in diff.low_confidence)
        )
    if not (diff.added or diff.discontinued or diff.hex_changed or diff.low_confidence):
        lines.append("- No material changes.")

    with path.open("a") as f:
        f.write("\n".join(lines) + "\n")
