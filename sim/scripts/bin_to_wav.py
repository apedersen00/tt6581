"""
Converts binary PDM data to audio file.
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
    file_size = os.path.getsize(PDM_FILE)
    total_pdm = file_size * 8  # each byte -> 8 bits
    duration = total_pdm / PDM_RATE
    print(f"PDM samples: {total_pdm:,} ({duration:.2f}s at {PDM_RATE/1e6:.0f} MHz)")

    sos = bessel(FILT_ORDER, FILT_CUTOFF, btype='low', fs=PDM_RATE, output='sos')
    decimation = PDM_RATE // TARGET_RATE

    # Process in streaming chunks: read raw bytes, unpack, filter, decimate.
    CHUNK_BYTES = 1_250_000  # 1.25 MB raw -> 10M PDM samples per chunk
    zi = np.zeros((sos.shape[0], 2), dtype=np.float64)
    audio_chunks = []
    phase = 0  # decimation phase carried across chunks

    samples_done = 0
    with open(PDM_FILE, 'rb') as f:
        while True:
            raw = np.frombuffer(f.read(CHUNK_BYTES), dtype=np.uint8)
            if len(raw) == 0:
                break
            pdm = np.unpackbits(raw).astype(np.float32)
            pdm = pdm * 2.0 - 1.0
            filtered, zi = sosfilt(sos, pdm, zi=zi)

            # Decimate with correct phase alignment across chunks
            decimated = filtered[phase::decimation]
            if len(decimated) > 0:
                audio_chunks.append(decimated.astype(np.float32))
            phase = (phase + len(filtered)) % decimation  # carry remainder

            samples_done += len(pdm)
            print(f"Processed {samples_done:,} / {total_pdm:,} samples...", end='\r')

            del raw, pdm, filtered  # free intermediates immediately

    print()
    audio = np.concatenate(audio_chunks)
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