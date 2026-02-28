"""
Results plotting.
"""

import os
import csv
import numpy as np
import matplotlib.pyplot as plt

from .constants import TB_OUTPUT_DIR, SAMPLE_RATE

def plot_envelope(samples, att, dec, sus, rel, gate_samps, filename: str = "audio_i_plot.png",
                       title: str = "Envelope",
                       sample_rate: int = SAMPLE_RATE):
    att_lut = [2, 8, 16, 24, 38, 56, 68, 80, 100, 250, 500, 800, 1000, 3000, 5000, 8000]
    dec_lut = [6, 24, 48, 72, 114, 168, 204, 240, 300, 750, 1500, 2400, 3000, 9000, 15000, 24000]

    t_ms = [i / sample_rate * 1000.0 for i in range(len(samples))]

    att = att_lut[att]
    dec = dec_lut[dec]
    sus = float(sus / 0xF)
    rel = dec_lut[rel]

    t_gate_off = t_ms[gate_samps]

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(t_ms, samples, color='blue', linewidth=2, alpha=0.7)
    ax.set_xlim(0, max(t_ms))

    peak = max(samples)
    sus_level = peak * sus

    env_style = dict(color='black', linewidth=2, alpha=0.8, linestyle='--')

    # Attack
    ax.plot((0, att), (0, peak), **env_style, label='Expected envelope')

    # Decay
    tau_dec = dec / 3
    if sus > 0:
        t_sus_cross = -tau_dec * np.log(sus)
    else:
        t_sus_cross = tau_dec * 5
    t_dec = np.linspace(0, t_sus_cross, 200)
    decay_curve = peak * np.exp(-t_dec / tau_dec)
    ax.plot(att + t_dec, decay_curve, **env_style)

    # Sustain
    t_dec_end = att + t_sus_cross
    ax.plot((t_dec_end, t_gate_off), (sus_level, sus_level), **env_style)

    ax.axvline(x=t_gate_off, color='red', linestyle=':', linewidth=1.5, alpha=0.8, label='Gate off')

    # Release
    tau_rel = rel / 3
    t_rel = np.linspace(0, rel, 200)
    release_curve = sus_level * np.exp(-t_rel / tau_rel)
    ax.plot(t_gate_off + t_rel, release_curve, **env_style)

    # ADSR info box
    adsr_text = (f"A = {att} ms\n"
                 f"D = {dec} ms\n"
                 f"S = {sus:.2f} ({int(sus * 0xF)}/15)\n"
                 f"R = {rel} ms")
    ax.text(0.98, 0.95, adsr_text, transform=ax.transAxes, fontsize=9,
            verticalalignment='top', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7),
            fontfamily='monospace')

    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("Amplitude")
    ax.set_title(title)
    ax.legend(loc='upper left')
    fig.tight_layout()
    plot_path = os.path.join(TB_OUTPUT_DIR, filename)
    fig.savefig(plot_path, dpi=150)

def plot_audio_samples(samples, filename: str = "audio_i_plot.png",
                       title: str = "PDM Reconstructed Audio",
                       sample_rate: int = SAMPLE_RATE):
    t_ms = [i / sample_rate * 1000.0 for i in range(len(samples))]

    plot_path = os.path.join(TB_OUTPUT_DIR, filename)
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(t_ms, samples, linewidth=2.0, color='black')
    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("Amplitude")
    ax.set_title(title)
    ax.axhline(0, color="grey", linewidth=0.3)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)


def plot_frequencies(samples,
                     expected_freqs: list[float],
                     filename: str = "freq_plot.png",
                     title: str = "Frequency analysis",
                     sample_rate: int = SAMPLE_RATE):
    N = len(samples)
    t_ms = [i / sample_rate * 1000.0 for i in range(N)]

    # FFT
    sig = np.array(samples, dtype=float)
    # Apply a Hann window to reduce spectral leakage
    window = np.hanning(N)
    sig_windowed = sig * window

    nfft = max(N, 4096)
    fft_vals = np.fft.rfft(sig_windowed, n=nfft)
    fft_mag = np.abs(fft_vals) / N
    freqs = np.fft.rfftfreq(nfft, d=1.0 / sample_rate)

    # Find 3 highest peaks
    mag_no_dc = fft_mag.copy()
    mag_no_dc[0] = 0
    peak_indices = []
    min_bin_gap = max(1, int(20 * N / sample_rate))

    for _ in range(3):
        idx = int(np.argmax(mag_no_dc))
        if mag_no_dc[idx] <= 0:
            break
        peak_indices.append(idx)
        lo = max(0, idx - min_bin_gap)
        hi = min(len(mag_no_dc), idx + min_bin_gap + 1)
        mag_no_dc[lo:hi] = 0

    detected_freqs = [float(freqs[i]) for i in peak_indices]

    # Plot
    plot_path = os.path.join(TB_OUTPUT_DIR, filename)
    fig, (ax_time, ax_fft) = plt.subplots(2, 1, figsize=(12, 7))
    fig.suptitle(title, fontsize=13, fontweight='bold')

    ax_time.plot(t_ms, samples, linewidth=1.2, color='black')
    ax_time.set_xlabel("Time (ms)")
    ax_time.set_ylabel("Amplitude")
    ax_time.axhline(0, color="grey", linewidth=0.3)
    ax_time.grid(True, alpha=0.3)

    ax_fft.plot(freqs, fft_mag, linewidth=2.0, color='black', label='FFT magnitude')

    for rank, idx in enumerate(peak_indices):
        ax_fft.plot(freqs[idx], fft_mag[idx], 'o', color='red', markersize=8)

    lines = []
    sorted_expected = sorted(expected_freqs)
    sorted_detected = sorted(detected_freqs)
    for j in range(min(3, len(sorted_detected))):
        exp = sorted_expected[j] if j < len(sorted_expected) else None
        det = sorted_detected[j]
        err = abs(det - exp) if exp is not None else float('nan')
        lines.append(f'Peak {j+1}: {det:.1f} Hz  (exp {exp:.1f}, err {err:.1f})')
    if lines:
        props = dict(boxstyle='round', facecolor='wheat', alpha=1.0)
        ax_fft.text(0.98, 0.25, '\n'.join(lines),
                    transform=ax_fft.transAxes, fontsize=9,
                    verticalalignment='top', horizontalalignment='right',
                    bbox=props)

    ax_fft.set_xlabel("Frequency (Hz)")
    ax_fft.set_ylabel("Magnitude")
    ax_fft.set_xlim(0, max(expected_freqs) * 1.3)
    ax_fft.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)

    return {
        'detected_freqs': detected_freqs,
        'expected_freqs': list(expected_freqs),
    }
