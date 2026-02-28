"""
Plots delta-sigma testbench output.
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import bessel, sosfilt

PDM_RATE    = 10_000_000   # 10 MHz PDM rate
TARGET_RATE = 50_000       # 50 kHz audio rate
DECIMATION  = PDM_RATE // TARGET_RATE  # 200
FILT_ORDER  = 4
FILT_CUTOFF = 20_000

TONE_FREQ   = 1000.0
SETTLE_TIME = 0.005

PDM_FILE = '../tmp/delta_sigma.bin'

def pdm_to_audio(pdm_path):
    """
    Decode packed binary PDM to audio samples.
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


def main():
    print("Reconstructing audio from PDM...")
    audio = pdm_to_audio(PDM_FILE)
    n = len(audio)
    print(f"Decoded {n} audio samples ({n / TARGET_RATE:.3f} s)")

    # Skip filter settle transient
    settle_samples = int(SETTLE_TIME * TARGET_RATE)
    audio = audio[settle_samples:]

    fig, ax = plt.subplots(2, 1, figsize=(12, 8))

    cycles_to_show = 3
    samples_per_cycle = TARGET_RATE / TONE_FREQ  # 50
    num_show = int(cycles_to_show * samples_per_cycle)
    time_ms = np.arange(num_show) / TARGET_RATE * 1000

    ax[0].plot(time_ms, audio[:num_show], color='black', linewidth=2)
    ax[0].set_title(f"Reconstructed {int(TONE_FREQ)} Hz Sine (Post 20 kHz Filter)")
    ax[0].set_xlabel("Time [ms]")
    ax[0].set_ylabel("Amplitude")
    ax[0].grid(linestyle='--', alpha=0.5)

    # FFT on full PDM stream for noise floor
    print("Calculating FFT...")
    with open(PDM_FILE, 'rb') as f:
        raw = np.frombuffer(f.read(), dtype=np.uint8)
    pdm_all = np.unpackbits(raw).astype(np.float32) * 2.0 - 1.0
    N = len(pdm_all)

    spectrum = np.fft.rfft(pdm_all)
    mag = np.abs(spectrum) / (N / 2)
    mag_db = 20 * np.log10(mag + 1e-12)
    freqs = np.fft.rfftfreq(N, d=1 / PDM_RATE)

    ax[1].semilogx(freqs, mag_db, color='black', alpha=0.8)
    ax[1].axvline(FILT_CUTOFF, color='grey', linestyle='--',
                  label=f'Audio Band ({FILT_CUTOFF / 1000:.0f} kHz)')
    ax[1].set_title("FFT Noise Floor")
    ax[1].set_xlabel("Frequency [Hz]")
    ax[1].set_ylabel("Magnitude [dB]")
    ax[1].set_ylim(-150, 0)
    ax[1].set_xlim(100, PDM_RATE / 2)
    ax[1].legend(loc='upper right')
    ax[1].grid(linestyle='--', which='both', alpha=0.5)

    plt.tight_layout()
    plt.savefig('../out/delta_sigma.png', dpi=400)
    print("Saved ../out/delta_sigma.png")

if __name__ == "__main__":
    main()