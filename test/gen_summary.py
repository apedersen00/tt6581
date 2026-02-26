#!/usr/bin/env python3

import argparse
import base64
import io
import os
import xml.etree.ElementTree as ET
from PIL import Image

RESULTS_XML = os.path.join(os.path.dirname(__file__), "results.xml")
PLOT_DIR = os.path.join(os.path.dirname(__file__), "tmp")

# GitHub step summary hard limit is 1024 kB.  Leave headroom for the
# Markdown text around the images.
MAX_SUMMARY_KB = 1024
TEXT_HEADROOM_KB = 24
MAX_IMAGE_BUDGET = (MAX_SUMMARY_KB - TEXT_HEADROOM_KB) * 1024  # bytes (base64)

# Target pixel width when down-scaling plots for the summary.
RESIZE_WIDTH = 720


def parse_results(xml_path: str) -> list[dict]:
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


def _compress_png(path: str) -> bytes:
    img = Image.open(path)

    # Down-scale if wider than target
    if img.width > RESIZE_WIDTH:
        ratio = RESIZE_WIDTH / img.width
        new_size = (RESIZE_WIDTH, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def img_tag(path: str, alt: str = "", width: int = 720) -> str:
    if not os.path.isfile(path):
        return f"*Plot not found: `{os.path.basename(path)}`*"
    png_bytes = _compress_png(path)
    data = base64.b64encode(png_bytes).decode()
    return f'<img src="data:image/png;base64,{data}" alt="{alt}" width="{width}">'


def generate_markdown() -> str:
    """Build the full Markdown summary string."""
    lines: list[str] = []
    lines.append("# TT6581 Test Results\n")

    #==================================
    # Test Table
    #==================================
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
    lines.append("## Waveform Test\n")
    lines.append("All four waveform types are generated at a frequency of 1kHz and plotted.")
    lines.append("Distortion occurs due to reconstruction from Delta-Sigma DAC.\n")

    path = os.path.join(PLOT_DIR, 'wave_triangle.png')
    lines.append(img_tag(path, alt='triangle waveform'))
    lines.append('')

    path = os.path.join(PLOT_DIR, 'wave_sawtooth.png')
    lines.append(img_tag(path, alt='sawtooth waveform'))
    lines.append('')

    path = os.path.join(PLOT_DIR, 'wave_pulse.png')
    lines.append(img_tag(path, alt='pulse waveform'))
    lines.append('')

    path = os.path.join(PLOT_DIR, 'wave_noise.png')
    lines.append(img_tag(path, alt='noise waveform'))
    lines.append('')

    #==================================
    # Frequency Test
    #==================================
    lines.append("## Frequency Test\n")
    lines.append("All three voices play triangle waves at different frequencies.")
    lines.append("The FFT shows peaks at the input frequencies.\n")

    path = os.path.join(PLOT_DIR, 'wave_freq_0.png')
    lines.append(img_tag(path, alt='frequency test 0'))
    lines.append('')

    path = os.path.join(PLOT_DIR, 'wave_freq_1.png')
    lines.append(img_tag(path, alt='frequency test 1'))
    lines.append('')

    #==================================
    # Envelope Test
    #==================================
    lines.append("## Envelope Test\n")
    lines.append("ADSR envelope shapes for different attack/decay/sustain/release settings.\n")

    path = os.path.join(PLOT_DIR, 'env_A0_D0_S15_R0.png')
    lines.append(img_tag(path, alt='envelope test 0'))
    lines.append('')

    path = os.path.join(PLOT_DIR, 'env_A4_D4_S10_R4.png')
    lines.append(img_tag(path, alt='envelope test 0'))
    lines.append('')

    #==================================
    # Filter Tests
    #==================================
    lines.append("## Filter Test\n")
    lines.append("Frequency response of the Chamberlin State-Variable Filter in all modes.\n")

    path = os.path.join(PLOT_DIR, 'filter_response_LP.png')
    lines.append(img_tag(path, alt='filter LP'))
    lines.append('')

    path = os.path.join(PLOT_DIR, 'filter_response_HP.png')
    lines.append(img_tag(path, alt='filter HP'))
    lines.append('')

    path = os.path.join(PLOT_DIR, 'filter_response_BP.png')
    lines.append(img_tag(path, alt='filter BP'))
    lines.append('')

    path = os.path.join(PLOT_DIR, 'filter_response_BR.png')
    lines.append(img_tag(path, alt='filter BR'))
    lines.append('')

    return "\n".join(lines)


def _truncate_to_budget(md: str) -> str:
    """If the summary exceeds the GitHub step summary limit, drop images
    from the bottom until it fits."""
    limit = MAX_SUMMARY_KB * 1024
    if len(md.encode()) <= limit:
        return md

    lines = md.split("\n")
    # Walk backwards, dropping <img …> lines until under budget
    while len("\n".join(lines).encode()) > limit and lines:
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip().startswith("<img "):
                lines[i] = "*Image omitted to fit GitHub summary size limit.*"
                break
        else:
            break  # no more images to drop

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o", "--output",
        help="Write summary to this file instead of GITHUB_STEP_SUMMARY",
    )
    args = parser.parse_args()

    md = generate_markdown()
    md = _truncate_to_budget(md)

    if args.output:
        with open(args.output, "w") as f:
            f.write(md)
        size_kb = len(md.encode()) / 1024
        print(f"Summary written to {args.output} ({size_kb:.0f} kB)")
        return

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a") as f:
            f.write(md)
        size_kb = len(md.encode()) / 1024
        print(f"Summary written to $GITHUB_STEP_SUMMARY ({size_kb:.0f} kB)")
    else:
        print(md)

if __name__ == "__main__":
    main()
