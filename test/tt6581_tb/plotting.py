# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

"""
Matplotlib plotting.
"""

import os
import csv
import numpy as np
import matplotlib.pyplot as plt

from .constants import TB_OUTPUT_DIR, SAMPLE_RATE

def plot_audio_samples(samples: list[int], filename: str = "audio_i_plot.png",
                       title: str = "delta_sigma.audio_i",
                       sample_rate: int = SAMPLE_RATE):
    """Save a time-domain plot of captured 14-bit signed audio samples as PNG.

    X-axis is time in milliseconds.  Also writes a CSV.
    """

    # Time axis in ms
    t_ms = [i / sample_rate * 1000.0 for i in range(len(samples))]

    # Write .csv
    csv_path = os.path.join(TB_OUTPUT_DIR, filename.rsplit(".", 1)[0] + ".csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time_ms", "audio_i"])
        for t, v in zip(t_ms, samples):
            writer.writerow([f"{t:.6f}", v])

    # Plot
    plot_path = os.path.join(TB_OUTPUT_DIR, filename)
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(t_ms, samples, linewidth=2.0, color='black')
    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("audio_i  (signed 14-bit)")
    ax.set_title(title)
    ax.set_ylim(-1024, 1023)
    ax.axhline(0, color="grey", linewidth=0.3)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)


def plot_frequencies(samples: list[int],
                     expected_freqs: list[float],
                     filename: str = "freq_plot.png",
                     title: str = "Frequency analysis",
                     sample_rate: int = SAMPLE_RATE):
    """Plot waveform + FFT side-by-side, marking the 3 highest FFT peaks.

    Parameters
    ----------
    samples : list[int]
        Signed 14-bit audio samples.
    expected_freqs : list[float]
        The three expected fundamental frequencies (Hz).
    filename : str
        Output PNG filename (saved under TB_OUTPUT_DIR).
    title : str
        Super-title for the figure.
    sample_rate : int
        Sample rate used during capture.

    Returns
    -------
    dict with ``detected_freqs`` (list of 3 peak frequencies in Hz) and
    ``expected_freqs``.
    """

    N = len(samples)
    t_ms = [i / sample_rate * 1000.0 for i in range(N)]

    # Write CSV
    csv_path = os.path.join(TB_OUTPUT_DIR, filename.rsplit(".", 1)[0] + ".csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time_ms", "audio_i"])
        for t, v in zip(t_ms, samples):
            writer.writerow([f"{t:.6f}", v])

    # FFT
    sig = np.array(samples, dtype=float)
    # Apply a Hann window to reduce spectral leakage
    window = np.hanning(N)
    sig_windowed = sig * window

    nfft = max(N, 4096)  # zero-pad for smoother spectrum
    fft_vals = np.fft.rfft(sig_windowed, n=nfft)
    fft_mag = np.abs(fft_vals) / N
    freqs = np.fft.rfftfreq(nfft, d=1.0 / sample_rate)

    # Find 3 highest peaks (skip DC bin)
    mag_no_dc = fft_mag.copy()
    mag_no_dc[0] = 0
    peak_indices = []
    min_bin_gap = max(1, int(20 * N / sample_rate))  # ~20 Hz exclusion zone

    for _ in range(3):
        idx = int(np.argmax(mag_no_dc))
        if mag_no_dc[idx] <= 0:
            break
        peak_indices.append(idx)
        # Zero out neighbourhood to find next independent peak
        lo = max(0, idx - min_bin_gap)
        hi = min(len(mag_no_dc), idx + min_bin_gap + 1)
        mag_no_dc[lo:hi] = 0

    detected_freqs = [float(freqs[i]) for i in peak_indices]

    # ── Plot ─────────────────────────────────────────────────────────────
    plot_path = os.path.join(TB_OUTPUT_DIR, filename)
    fig, (ax_time, ax_fft) = plt.subplots(2, 1, figsize=(12, 7))
    fig.suptitle(title, fontsize=13, fontweight='bold')

    # -- Time-domain subplot --
    ax_time.plot(t_ms, samples, linewidth=1.2, color='black')
    ax_time.set_xlabel("Time (ms)")
    ax_time.set_ylabel("audio_i  (signed 14-bit)")
    ax_time.set_ylim(-2048, 2047)
    ax_time.axhline(0, color="grey", linewidth=0.3)
    ax_time.grid(True, alpha=0.3)

    # -- FFT subplot --
    ax_fft.plot(freqs, fft_mag, linewidth=2.0, color='black', label='FFT magnitude')

    # Mark detected peaks — labels at a fixed y position
    label_y = 105  # fixed height for all labels
    for rank, idx in enumerate(peak_indices):
        ax_fft.plot(freqs[idx], fft_mag[idx], 'o', color='red', markersize=8)
        ax_fft.annotate(
            f'{freqs[idx]:.1f} Hz',
            xy=(freqs[idx], fft_mag[idx]),
            xytext=(freqs[idx], label_y + rank * 8),
            textcoords='data',
            arrowprops=dict(arrowstyle='->', color='red', lw=1.0),
            color='red', fontsize=9, fontweight='bold', ha='center',
        )

    # Summary text box
    lines = []
    sorted_expected = sorted(expected_freqs)
    sorted_detected = sorted(detected_freqs)
    for j in range(min(3, len(sorted_detected))):
        exp = sorted_expected[j] if j < len(sorted_expected) else None
        det = sorted_detected[j]
        err = abs(det - exp) if exp is not None else float('nan')
        lines.append(f'Peak {j+1}: {det:.1f} Hz  (exp {exp:.1f}, err {err:.1f})')
    if lines:
        props = dict(boxstyle='round', facecolor='wheat', alpha=0.7)
        ax_fft.text(0.98, 0.75, '\n'.join(lines),
                    transform=ax_fft.transAxes, fontsize=9,
                    verticalalignment='top', horizontalalignment='right',
                    bbox=props)

    ax_fft.set_xlabel("Frequency (Hz)")
    ax_fft.set_ylabel("Magnitude")
    ax_fft.set_xlim(0, max(expected_freqs) * 1.3)
    ax_fft.set_ylim(0, 140)
    ax_fft.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)

    return {
        'detected_freqs': detected_freqs,
        'expected_freqs': list(expected_freqs),
    }
