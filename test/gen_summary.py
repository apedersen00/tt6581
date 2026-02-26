#!/usr/bin/env python3

import argparse
import base64
import os
import xml.etree.ElementTree as ET

RESULTS_XML = os.path.join(os.path.dirname(__file__), "results.xml")
PLOT_DIR = os.path.join(os.path.dirname(__file__), "tmp")

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


def img_tag(path: str, alt: str = "", width: int = 800) -> str:
    if not os.path.isfile(path):
        return f"*Plot not found: `{os.path.basename(path)}`*"
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
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
    # Filter Test
    #==================================
    lines.append("## Filter Test\n")
    lines.append("Frequency response of the Chamberlin State-Variable Filter in all modes.\n")

    path = os.path.join(PLOT_DIR, 'env_A4_D4_S10_R4.png')
    lines.append(img_tag(path, alt='envelope test 0'))
    lines.append('')

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o", "--output",
        help="Write summary to this file instead of GITHUB_STEP_SUMMARY",
    )
    args = parser.parse_args()

    md = generate_markdown()

    if args.output:
        with open(args.output, "w") as f:
            f.write(md)
        print(f"Summary written to {args.output}")
        return

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a") as f:
            f.write(md)
        print(f"Summary written to $GITHUB_STEP_SUMMARY")
    else:
        print(md)

if __name__ == "__main__":
    main()
