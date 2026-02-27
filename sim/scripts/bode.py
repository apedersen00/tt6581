"""
Plots TT6581 natural frequency response from bode testbench output.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import bessel, sosfilt

PDM_RATE    = 10_000_000   # 10 MHz PDM rate
TARGET_RATE = 50_000       # 50 kHz audio rate (matches sim SAMPLE_RATE)
DECIMATION  = PDM_RATE // TARGET_RATE  # 200
FILT_ORDER  = 4
FILT_CUTOFF = 20_000       # low-pass for PDM reconstruction

SETTLE_TIME = 0.05

PDM_FILE = '../tmp/bode.bin'
CSV_FILE = '../tmp/bode.csv'

def pdm_to_audio(pdm_path):
    """
    Decode PDM output.
    """
    sos = bessel(FILT_ORDER, FILT_CUTOFF, btype='low', fs=PDM_RATE, output='sos')
    zi = np.zeros((sos.shape[0], 2), dtype=np.float64)

    CHUNK_BYTES = 1_250_000
    audio_chunks = []
    phase = 0

    with open(pdm_path, 'rb') as f:
        while True:
            raw = np.frombuffer(f.read(CHUNK_BYTES), dtype=np.uint8)
            if len(raw) == 0:
                break
            pdm = np.unpackbits(raw).astype(np.float32)
            pdm = pdm * 2.0 - 1.0
            filtered, zi = sosfilt(sos, pdm, zi=zi)

            decimated = filtered[phase::DECIMATION]
            if len(decimated) > 0:
                audio_chunks.append(decimated.astype(np.float32))
            phase = (phase + len(filtered)) % DECIMATION

            del raw, pdm, filtered

    return np.concatenate(audio_chunks)

def plot_bode():
    print("Reconstructing audio from PDM...")
    audio = pdm_to_audio(PDM_FILE)

    # Read frequency schedule
    sched = pd.read_csv(CSV_FILE)
    freqs = sched["freq_hz"].to_numpy()

    # Trim settle period
    settle_samples = int(SETTLE_TIME * TARGET_RATE)
    audio = audio[settle_samples:]

    # Align lengths
    n = min(len(audio), len(freqs))
    audio = audio[:n]
    freqs = freqs[:n]

    unique_freqs = []
    rms_vals = []

    freq_changes = np.where(np.diff(freqs) != 0)[0] + 1
    boundaries = np.concatenate([[0], freq_changes, [n]])

    for i in range(len(boundaries) - 1):
        start = boundaries[i]
        end = boundaries[i + 1]
        block = audio[start:end]

        skip = max(1, len(block) // 4)
        steady = block[skip:]

        if len(steady) > 0:
            unique_freqs.append(freqs[start])
            rms_vals.append(np.sqrt(np.mean(steady ** 2)))

    unique_freqs = np.array(unique_freqs)
    rms_vals = np.array(rms_vals)

    # Normalize to 0 dB at peak
    rms_vals = np.where(rms_vals < 1e-12, 1e-12, rms_vals)
    gain_db = 20 * np.log10(rms_vals / np.max(rms_vals))

    # Plot
    fig, ax = plt.subplots(figsize=(12, 4))

    # Frequency response
    ax.semilogx(unique_freqs, gain_db, color='black', linewidth=2.0)
    ax.axhline(-3, color='grey', linestyle='-', alpha=0.5, label='-3 dB')
    ax.set_ylabel("Magnitude [dB]")
    ax.set_xlabel("Frequency [Hz]")
    ax.set_ylim(-50, 5)
    ax.set_xlim(20, 20000)
    ax.set_title("TT6581 Frequency Response (Triangle, Filter Bypassed)")
    ax.grid(which='both', linestyle='--', alpha=0.5)
    ax.legend(loc='upper right')

    plt.tight_layout()
    plt.savefig("../out/bode.png", dpi=400)
    print(f"Saved ../out/bode.png")

def main():
    plot_bode()

if __name__ == "__main__":
    main()
