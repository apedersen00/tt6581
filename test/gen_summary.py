#!/usr/bin/env python3
"""Generate a Markdown test summary with embedded plots for GitHub Actions."""

import base64
import glob
import os
import sys
import xml.etree.ElementTree as ET

RESULTS_XML = os.path.join(os.path.dirname(__file__), "results.xml")
PLOT_DIR = os.path.join(os.path.dirname(__file__), "tmp")


def parse_results(xml_path: str) -> list[dict]:
    """Parse JUnit XML and return a list of test-case dicts."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    cases = []
    for tc in root.iter("testcase"):
        status = "passed"
        message = ""
        failure = tc.find("failure")
        if failure is not None:
            status = "failed"
            message = failure.get("message", "")
        cases.append({
            "name": tc.get("name", "unknown"),
            "classname": tc.get("classname", ""),
            "time": tc.get("time", "0"),
            "status": status,
            "message": message,
        })
    return cases


def img_tag(path: str, alt: str = "", width: int = 800) -> str:
    """Return an HTML <img> tag with the file base64-encoded inline."""
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    return f'<img src="data:image/png;base64,{data}" alt="{alt}" width="{width}">'


def generate_markdown() -> str:
    """Build the full Markdown summary string."""
    lines: list[str] = []
    lines.append("# TT6581 Test Results\n")

    # ── Test table ───────────────────────────────────────────────────────
    if os.path.isfile(RESULTS_XML):
        cases = parse_results(RESULTS_XML)
        lines.append("## Test Cases\n")
        lines.append("| Test | Status | Time |")
        lines.append("|------|--------|------|")
        for tc in cases:
            icon = "✅" if tc["status"] == "passed" else "❌"
            lines.append(f"| `{tc['name']}` | {icon} {tc['status']} | {tc['time']}s |")
        lines.append("")
    else:
        lines.append("> ⚠️ `results.xml` not found — skipping test table.\n")

    # ── Plots ────────────────────────────────────────────────────────────
    pngs = sorted(glob.glob(os.path.join(PLOT_DIR, "*.png")))
    if pngs:
        lines.append("## Plots\n")
        for png in pngs:
            name = os.path.splitext(os.path.basename(png))[0]
            title = name.replace("_", " ").title()
            lines.append(f"### {title}\n")
            lines.append(img_tag(png, alt=title))
            lines.append("")
    else:
        lines.append("> No plots found in `test/tmp/`.\n")

    return "\n".join(lines)


def main():
    md = generate_markdown()

    # Write to $GITHUB_STEP_SUMMARY if available (CI), else stdout
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a") as f:
            f.write(md)
        print(f"Summary written to $GITHUB_STEP_SUMMARY ({len(md)} chars)")
    else:
        print(md)


if __name__ == "__main__":
    main()
