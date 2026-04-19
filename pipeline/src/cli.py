"""fabric-colors pipeline CLI.

Usage:
    python pipeline/src/cli.py run --line robert-kaufman/kona-cotton
    python pipeline/src/cli.py run --line robert-kaufman/kona-cotton --skip-vision
    python pipeline/src/cli.py run --line robert-kaufman/kona-cotton \\
        --summary-json /tmp/summary.json

--skip-vision runs discover/fetch/parse/algorithmic only, then exits
without writing a data file. Useful for verifying the scrape half of the
pipeline without an Anthropic API key.

--summary-json writes a machine-readable summary of the run (counts,
changed IDs, before/after hex values, halt flag) to the given path.
Consumed by the weekly-update GitHub Actions workflow.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

# Ensure sibling modules resolve whether run as a script or via -m.
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import config as config_mod  # noqa: E402
import discover as discover_mod  # noqa: E402
import extract as extract_mod  # noqa: E402
import extract_algorithmic  # noqa: E402
import fetch as fetch_mod  # noqa: E402
import image_utils  # noqa: E402
import merge as merge_mod  # noqa: E402
import parse as parse_mod  # noqa: E402
import validate as validate_mod  # noqa: E402
import write as write_mod  # noqa: E402

# Halt thresholds per docs/project-plan.md. Denominator is the count of
# colors actually processed this run (the extraction set), not the full
# record set (which may include carry-overs from prior runs).
HEX_CHANGE_HALT_RATE = 0.20
LOW_CONFIDENCE_HALT_RATE = 0.10


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="fabric-colors")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run the full pipeline for one line.")
    run.add_argument(
        "--line", required=True,
        help="Line path under configs/, e.g. robert-kaufman/kona-cotton",
    )
    run.add_argument(
        "--skip-vision", action="store_true",
        help="Run through parse + algorithmic only; do not call Claude.",
    )
    run.add_argument(
        "--summary-json",
        help="Write a machine-readable run summary to this path.",
    )

    args = parser.parse_args(argv)
    if args.command == "run":
        return _cmd_run(
            args.line,
            skip_vision=args.skip_vision,
            summary_path=args.summary_json,
        )
    return 2


def _cmd_run(
    line_path: str,
    *,
    skip_vision: bool,
    summary_path: str | None,
) -> int:
    today = date.today()
    cfg = config_mod.load(line_path)
    print(f"config: {cfg.manufacturer.slug}/{cfg.line.slug} "
          f"({len(cfg.skus)} SKU(s))")

    discovered = discover_mod.discover(cfg)
    print(f"discover: {len(discovered)} URL(s)")

    fetched = fetch_mod.fetch(cfg, discovered)
    print(f"fetch: {len(fetched)} page(s) + image(s) downloaded")

    parsed = parse_mod.parse(fetched, cfg)
    for item in parsed:
        print(f"  parse: {item.sku} -> {item.name!r}")

    if skip_vision:
        print("skip-vision: computing algorithmic hex + routing, no data file written")
        vision_count = 0
        for item in parsed:
            rgb = image_utils.load_and_preprocess(item.image_path)
            algo = extract_algorithmic.extract(rgb)
            classification = extract_mod._classify(algo, rgb)
            if classification == "photograph":
                vision_count += 1
            print(f"  algo: {item.sku} {item.name!r} -> "
                  f"{algo.hex} (std_dev={algo.std_dev:.2f}) [{classification}]")
        print(f"skip-vision: {vision_count}/{len(parsed)} images would route to vision")
        return 0

    extractions = extract_mod.extract(parsed)
    for ex in extractions:
        if ex.vision is None:
            print(
                f"  extract: {ex.parsed.sku} {ex.parsed.name!r} "
                f"[{ex.classification}] algo={ex.algorithmic.hex} "
                f"-> {ex.final_hex} "
                f"[{ex.final_method}, {ex.final_confidence}]"
            )
        else:
            print(
                f"  extract: {ex.parsed.sku} {ex.parsed.name!r} "
                f"[{ex.classification}] vision={ex.vision.hex} "
                f"algo={ex.algorithmic.hex} ΔE={ex.delta_e:.2f} "
                f"-> {ex.final_hex} "
                f"[{ex.final_method}, {ex.final_confidence}]"
            )

    prior_version = write_mod.load_prior_data_version(cfg)
    prior_colors_by_id = _load_prior_colors_by_id(write_mod.data_path(cfg))
    records, diff = merge_mod.merge(
        extractions, cfg, write_mod.data_path(cfg), today
    )

    halt_reason = _check_halt(diff, processed_count=len(extractions))
    if halt_reason is not None:
        print(f"HALT: {halt_reason}", file=sys.stderr)
        if summary_path:
            _write_summary(
                Path(summary_path),
                line_path=line_path,
                prior_version=prior_version,
                new_version=None,
                diff=diff,
                records=records,
                prior_colors_by_id=prior_colors_by_id,
                halt_reason=halt_reason,
            )
        return 2

    data_path, new_version = write_mod.write(
        cfg, records, diff, today, prior_version
    )
    print(f"wrote: {data_path} (data_version {prior_version} -> {new_version})")

    validate_mod.validate_file(data_path)
    print("validate: ok")

    index_p = write_mod.write_index(today)
    validate_mod.validate_index_file(index_p)
    print(f"wrote: {index_p}")

    _print_summary(diff)

    if summary_path:
        _write_summary(
            Path(summary_path),
            line_path=line_path,
            prior_version=prior_version,
            new_version=new_version,
            diff=diff,
            records=records,
            prior_colors_by_id=prior_colors_by_id,
            halt_reason=None,
        )
    return 0


def _check_halt(diff, *, processed_count: int) -> str | None:
    if processed_count == 0:
        return None
    hex_rate = len(diff.hex_changed) / processed_count
    low_rate = len(diff.low_confidence) / processed_count
    if hex_rate > HEX_CHANGE_HALT_RATE:
        return (
            f"hex_change_rate={hex_rate:.1%} exceeds "
            f"{HEX_CHANGE_HALT_RATE:.0%} — manual investigation needed"
        )
    if low_rate > LOW_CONFIDENCE_HALT_RATE:
        return (
            f"low_confidence_rate={low_rate:.1%} exceeds "
            f"{LOW_CONFIDENCE_HALT_RATE:.0%} — manual investigation needed"
        )
    return None


def _print_summary(diff) -> None:
    print("summary:")
    print(f"  added:          {len(diff.added)}")
    print(f"  discontinued:   {len(diff.discontinued)}")
    print(f"  hex_changed:    {len(diff.hex_changed)}")
    print(f"  low_confidence: {len(diff.low_confidence)}")
    if diff.low_confidence:
        print("  low-confidence IDs:")
        for cid in diff.low_confidence:
            print(f"    - {cid}")


def _load_prior_colors_by_id(data_path: Path) -> dict:
    if not data_path.exists():
        return {}
    with data_path.open() as f:
        doc = json.load(f)
    return {c["id"]: c for c in doc.get("colors", [])}


def _write_summary(
    path: Path,
    *,
    line_path: str,
    prior_version: str,
    new_version: str | None,
    diff,
    records,
    prior_colors_by_id: dict,
    halt_reason: str | None,
) -> None:
    records_by_id = {r.id: r for r in records}

    added_details = []
    for cid in diff.added:
        r = records_by_id.get(cid)
        if r is not None:
            added_details.append(
                {"id": r.id, "name": r.name, "sku": r.sku, "hex": r.hex}
            )

    discontinued_details = []
    for cid in diff.discontinued:
        r = records_by_id.get(cid) or prior_colors_by_id.get(cid)
        if r is None:
            continue
        if hasattr(r, "name"):
            discontinued_details.append(
                {"id": r.id, "name": r.name, "sku": r.sku}
            )
        else:
            discontinued_details.append(
                {"id": r["id"], "name": r["name"], "sku": r["sku"]}
            )

    hex_change_details = []
    for cid in diff.hex_changed:
        new = records_by_id.get(cid)
        prev = prior_colors_by_id.get(cid)
        if new is None or prev is None:
            continue
        hex_change_details.append(
            {
                "id": cid,
                "name": new.name,
                "sku": new.sku,
                "before": prev["hex"],
                "after": new.hex,
            }
        )

    low_confidence_details = []
    for cid in diff.low_confidence:
        r = records_by_id.get(cid)
        if r is not None:
            low_confidence_details.append(
                {
                    "id": r.id,
                    "name": r.name,
                    "sku": r.sku,
                    "hex": r.hex,
                    "manufacturer_product_url": r.manufacturer_product_url,
                }
            )

    payload = {
        "line": line_path,
        "prior_data_version": prior_version,
        "new_data_version": new_version,
        "halt": halt_reason,
        "changed": bool(
            diff.added or diff.discontinued or diff.hex_changed
        ),
        "counts": {
            "added": len(diff.added),
            "discontinued": len(diff.discontinued),
            "hex_changed": len(diff.hex_changed),
            "low_confidence": len(diff.low_confidence),
            "records": len(records),
        },
        "added": added_details,
        "discontinued": discontinued_details,
        "hex_changed": hex_change_details,
        "low_confidence": low_confidence_details,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
