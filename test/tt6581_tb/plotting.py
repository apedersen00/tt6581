# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

"""Matplotlib plotting and CSV export helpers."""

import os

from .constants import TB_OUTPUT_DIR, SAMPLE_RATE


def plot_audio_samples(samples: list[int], filename: str = "audio_i_plot.png",
                       title: str = "delta_sigma.audio_i",
                       sample_rate: int = SAMPLE_RATE):
    """Save a time-domain plot of captured 14-bit signed audio samples as PNG.

    X-axis is time in milliseconds.  Also writes a companion CSV.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import csv

    # Time axis in ms
    t_ms = [i / sample_rate * 1000.0 for i in range(len(samples))]

    # ── Write CSV ────────────────────────────────────────────────────────────
    csv_path = os.path.join(TB_OUTPUT_DIR, filename.rsplit(".", 1)[0] + ".csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time_ms", "audio_i"])
        for t, v in zip(t_ms, samples):
            writer.writerow([f"{t:.6f}", v])

    # ── Plot ─────────────────────────────────────────────────────────────────
    plot_path = os.path.join(TB_OUTPUT_DIR, filename)
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(t_ms, samples, linewidth=0.6)
    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("audio_i  (signed 14-bit)")
    ax.set_title(title)
    ax.set_ylim(-1024, 1023)
    ax.axhline(0, color="grey", linewidth=0.3)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)


def plot_multi_overlay(all_traces: list[tuple[str, list[int]]],
                       filename: str, title: str,
                       sample_rate: int = SAMPLE_RATE):
    """Plot multiple sample traces overlaid on the same axes."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(14, 5))
    for label, samples in all_traces:
        t_ms = [i / sample_rate * 1000.0 for i in range(len(samples))]
        ax.plot(t_ms, samples, linewidth=0.6, label=label)
    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("audio_i  (signed 14-bit)")
    ax.set_title(title)
    ax.set_ylim(-1024, 1023)
    ax.axhline(0, color="grey", linewidth=0.3)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(TB_OUTPUT_DIR, filename), dpi=150)
    plt.close(fig)
