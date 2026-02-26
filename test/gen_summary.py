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
            icon = "Pass" if tc["status"] == "passed" else "Fail"
            lines.append(f"| `{tc['name']}` | {icon} {tc['status']} | {tc['time']}s |")
        lines.append("")

    #==================================
    # Waveform Test
    #==================================
    lines.append('## Waveform Test')
    lines.append('All four supported waveform types are generated at a frequency of 1kHz and plotted.')
    lines.append('Distortion occurs due to reconstruction from Delta-Sigma DAC.')

    path = os.path.join(PLOT_DIR, 'wave_triangle.png')
    lines.append(img_tag(path, alt='path'))

    path = os.path.join(PLOT_DIR, 'wave_sawtooth.png')
    lines.append(img_tag(path, alt='path'))

    path = os.path.join(PLOT_DIR, 'wave_pulse.png')
    lines.append(img_tag(path, alt='path'))

    path = os.path.join(PLOT_DIR, 'wave_noise.png')
    lines.append(img_tag(path, alt='path'))

    #==================================
    # Frequency Test
    #==================================
    lines.append('## Frequency Test')
    lines.append('All three voices play triangle waves at different frequencies.')
    lines.append('The FFT shows peaks at the input frequencies.')

    path = os.path.join(PLOT_DIR, 'wabe_freq_0.png')
    lines.append(img_tag(path, alt='path'))

    path = os.path.join(PLOT_DIR, 'wabe_freq_1.png')
    lines.append(img_tag(path, alt='path'))

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
