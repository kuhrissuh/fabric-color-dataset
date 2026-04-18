"""Validate a fabric color data file against the v1 schema and structural rules."""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

import jsonschema

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "schemas" / "v1.json"


class ValidationError(Exception):
    """Raised when a data file violates a structural rule beyond the JSON Schema."""


def slugify(value: str) -> str:
    """Lowercase and collapse non-alphanumerics to single hyphens."""
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def load_schema() -> dict[str, Any]:
    with SCHEMA_PATH.open() as f:
        return json.load(f)


def validate(data: dict[str, Any]) -> None:
    """Validate a parsed data file. Raises on first failure."""
    jsonschema.Draft202012Validator(load_schema()).validate(data)
    _check_structural(data)


def validate_file(path: Path) -> None:
    with path.open() as f:
        validate(json.load(f))


def _check_structural(data: dict[str, Any]) -> None:
    errors: list[str] = []
    colors = data["colors"]

    if data["color_count"] != len(colors):
        errors.append(
            f"color_count ({data['color_count']}) != len(colors) ({len(colors)})"
        )

    manufacturer_slug = data["manufacturer"]["slug"]
    line_slug = data["line"]["slug"]
    generated_on = date.fromisoformat(data["generated_on"])

    seen_ids: set[str] = set()
    for i, color in enumerate(colors):
        cid = color["id"]
        expected = f"{manufacturer_slug}-{line_slug}-{slugify(color['sku'])}"
        if cid != expected:
            errors.append(
                f"colors[{i}] id {cid!r} != expected {expected!r} "
                f"(manufacturer.slug + line.slug + slugify(sku))"
            )
        if cid in seen_ids:
            errors.append(f"colors[{i}] duplicate id {cid!r}")
        seen_ids.add(cid)

        first_seen = date.fromisoformat(color["first_seen"])
        collected = date.fromisoformat(color["source_collected_on"])
        if first_seen > collected:
            errors.append(
                f"colors[{i}] ({cid}) first_seen {first_seen} > "
                f"source_collected_on {collected}"
            )
        if collected > generated_on:
            errors.append(
                f"colors[{i}] ({cid}) source_collected_on {collected} > "
                f"generated_on {generated_on}"
            )

    if errors:
        raise ValidationError("\n".join(errors))


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: validate.py <path> [<path>...]", file=sys.stderr)
        return 2
    ok = True
    for arg in argv:
        path = Path(arg)
        try:
            validate_file(path)
        except jsonschema.ValidationError as e:
            location = "/".join(str(p) for p in e.absolute_path) or "<root>"
            print(f"{path}: schema error at {location}: {e.message}", file=sys.stderr)
            ok = False
        except ValidationError as e:
            print(f"{path}: {e}", file=sys.stderr)
            ok = False
        else:
            print(f"{path}: ok")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
