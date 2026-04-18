"""fabric-colors pipeline CLI.

Usage:
    python pipeline/src/cli.py run --line robert-kaufman/kona-cotton
    python pipeline/src/cli.py run --line robert-kaufman/kona-cotton --skip-vision

--skip-vision runs discover/fetch/parse/algorithmic only, then exits
without writing a data file. Useful for verifying the scrape half of the
pipeline without an Anthropic API key.
"""

from __future__ import annotations

import argparse
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

    args = parser.parse_args(argv)
    if args.command == "run":
        return _cmd_run(args.line, skip_vision=args.skip_vision)
    return 2


def _cmd_run(line_path: str, *, skip_vision: bool) -> int:
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
        print("skip-vision: computing algorithmic hex only, no data file written")
        for item in parsed:
            rgb = image_utils.load_and_preprocess(item.image_path)
            algo = extract_algorithmic.extract(rgb)
            print(f"  algo: {item.sku} {item.name!r} -> "
                  f"{algo.hex} (std_dev={algo.std_dev:.2f})")
        return 0

    extractions = extract_mod.extract(parsed)
    for ex in extractions:
        print(
            f"  extract: {ex.parsed.sku} {ex.parsed.name!r} "
            f"vision={ex.vision.hex} algo={ex.algorithmic.hex} "
            f"ΔE={ex.delta_e:.2f} -> {ex.final_hex} "
            f"[{ex.final_method}, {ex.final_confidence}]"
        )

    prior_version = write_mod.load_prior_data_version(cfg)
    records, diff = merge_mod.merge(
        extractions, cfg, write_mod.data_path(cfg), today
    )
    data_path, new_version = write_mod.write(
        cfg, records, diff, today, prior_version
    )
    print(f"wrote: {data_path} (data_version {prior_version} -> {new_version})")

    validate_mod.validate_file(data_path)
    print("validate: ok")

    _print_summary(diff)
    return 0


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


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
