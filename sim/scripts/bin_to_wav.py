"""
Converts binary PDM data to audio file.
"""

"""
Parses envelope testbench output.
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import butter, bessel, sosfilt
from scipy.io import wavfile

PDM_FILE    = '../tmp/pdm_out.bin'
OUTPUT_WAV  = '../out/audio.wav'
PDM_RATE    = 10_000_000  # 10 MHz PDM sample rate
TARGET_RATE = 50_000      # Target audio sample rate
FILT_ORDER  = 4           # Filter order
FILT_CUTOFF = 20_000      # Low-pass cutoff

def main():
    raw = np.fromfile(PDM_FILE, dtype=np.uint8)
    pdm = np.unpackbits(raw).astype(np.float32)

    duration = len(pdm) / PDM_RATE
    print(f"PDM samples: {len(pdm):,} ({duration:.2f}s at {PDM_RATE/1e6:.0f} MHz)")

    pdm = pdm * 2.0 - 1.0

    sos = bessel(FILT_ORDER, FILT_CUTOFF, btype='low', fs=PDM_RATE, output='sos')

    # Apply filter in chunks
    CHUNK = 10_000_000
    zi = np.zeros((sos.shape[0], 2), dtype=np.float64)
    filtered_chunks = []

    for start in range(0, len(pdm), CHUNK):
        end = min(start + CHUNK, len(pdm))
        chunk_out, zi = sosfilt(sos, pdm[start:end], zi=zi)
        filtered_chunks.append(chunk_out)
        print(f"Filtered {end:,} / {len(pdm):,} samples...", end='\r')

    filtered = np.concatenate(filtered_chunks)
    print()

    # Downsample: 10 MHz -> 50 kHz
    decimation = PDM_RATE // TARGET_RATE
    audio = filtered[::decimation]
    print(f"Downsampled ÷{decimation}: {len(audio):,} samples at {TARGET_RATE/1e3:.0f} kHz")

    # Normalize to [-1, 1]
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak

    # Save WAV
    wavfile.write(OUTPUT_WAV, TARGET_RATE, audio.astype(np.float32))
    print(f"Saved {OUTPUT_WAV} ({len(audio):,} samples, {len(audio)/TARGET_RATE:.2f}s)")

    # plot
    t = np.arange(len(audio)) / TARGET_RATE

    fig, axes = plt.subplots(2, 1, figsize=(14, 8))
    axes[0].plot(t, audio, color='teal', linewidth=0.5)
    axes[0].set_title(f'Reconstructed Audio ({FILT_ORDER}th-order Butterworth LP @ {FILT_CUTOFF/1e3:.0f} kHz)')
    axes[0].set_xlabel('Time [s]')
    axes[0].set_ylabel('Amplitude')
    axes[0].grid(linestyle='--', alpha=0.5)

    # Zoomed view (~20ms window at midpoint)
    mid = len(audio) // 2
    window = int(0.02 * TARGET_RATE)
    sl = slice(max(0, mid - window), min(len(audio), mid + window))
    axes[1].plot(t[sl], audio[sl], color='black', linewidth=2.0)
    axes[1].set_title('Zoomed View (20 ms)')
    axes[1].set_xlabel('Time [s]')
    axes[1].set_ylabel('Amplitude')
    axes[1].grid(linestyle='--', alpha=0.5)

    plt.tight_layout()
    plt.savefig('../out/audio.png', dpi=400)

if __name__ == "__main__":
    main()