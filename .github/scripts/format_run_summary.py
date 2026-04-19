"""Render a pipeline run summary JSON as the weekly-update PR body
(and the workflow job step summary on the same markdown).

Usage:
    python format_run_summary.py <summary.json> <run_date>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def render(summary: dict, run_date: str) -> str:
    line = summary.get("line", "?")
    halt = summary.get("halt")
    prior = summary.get("prior_data_version")
    new = summary.get("new_data_version")
    counts = summary.get("counts", {})

    lines: list[str] = [f"## Weekly update — {run_date}", ""]
    lines.append(f"Line: `{line}`")

    if halt:
        lines.append("")
        lines.append(f"### HALT")
        lines.append("")
        lines.append(f"> {halt}")
        lines.append("")
        lines.append("Pipeline stopped before writing. Manual investigation required.")
        return "\n".join(lines) + "\n"

    version_line = f"data_version: `{prior}`"
    if new and new != prior:
        version_line += f" → `{new}`"
    lines.append(version_line)
    lines.append("")

    lines.append("### Summary")
    lines.append(f"- Added: {counts.get('added', 0)}")
    lines.append(f"- Discontinued: {counts.get('discontinued', 0)}")
    lines.append(f"- Hex updated: {counts.get('hex_changed', 0)}")
    lines.append(f"- Low-confidence: {counts.get('low_confidence', 0)}")
    lines.append("")

    added = summary.get("added") or []
    if added:
        lines.append("### Added")
        for a in added:
            lines.append(
                f"- `{a['id']}` \"{a['name']}\" ({a['sku']}) — {a['hex']}"
            )
        lines.append("")

    discontinued = summary.get("discontinued") or []
    if discontinued:
        lines.append("### Discontinued")
        for d in discontinued:
            lines.append(f"- `{d['id']}` \"{d['name']}\" ({d['sku']})")
        lines.append("")

    hex_changed = summary.get("hex_changed") or []
    if hex_changed:
        lines.append("### Hex updates")
        for h in hex_changed:
            lines.append(
                f"- `{h['id']}` \"{h['name']}\" ({h['sku']}): "
                f"{h['before']} → {h['after']}"
            )
        lines.append("")

    low_conf = summary.get("low_confidence") or []
    lines.append("### Low-confidence (review needed)")
    if low_conf:
        for lc in low_conf:
            url = lc.get("manufacturer_product_url", "")
            url_suffix = f" — [source]({url})" if url else ""
            lines.append(
                f"- `{lc['id']}` \"{lc['name']}\" ({lc['sku']}) "
                f"current: {lc['hex']}{url_suffix}"
            )
    else:
        lines.append("None this run.")
    lines.append("")

    lines.append("### Validation")
    lines.append("All checks passed.")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: format_run_summary.py <summary.json> <run_date>", file=sys.stderr)
        return 2
    summary_path, run_date = argv
    summary = json.loads(Path(summary_path).read_text())
    sys.stdout.write(render(summary, run_date))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
