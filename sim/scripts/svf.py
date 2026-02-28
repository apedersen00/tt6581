"""
Parses svf testbench output.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def get_envelope(sig, window=100):
    return pd.Series(sig).abs().rolling(window=window, center=True).max()

def plot_response(file):
    name = file.split('/')[-1].split('.')[0].split('_')[-1]
    df = pd.read_csv(file)

    input_sig = df['in_val'] / 8192.0
    output_sig = df['out_val'] / 8192.0

    time = df['time_sec']
    freqs = df['freq_hz']

    input_env = get_envelope(input_sig, window=200)
    output_env = get_envelope(output_sig, window=200)

    # Prevent log10(0) errors
    output_env = output_env.replace(0, 1e-9)
    input_env = input_env.replace(0, 1e-9)

    gain_db = 20 * np.log10(output_env / input_env)

    fig, ax = plt.subplots(2, 1, figsize=(12, 8))

    # Plot time domain
    ax[0].set_title("Time Domain")
    ax[0].plot(time, input_sig, color='black', linewidth=2, label="Input", alpha=1.0)
    ax[0].plot(time, output_sig, color='blue', linewidth=2, label="Output", alpha=0.5)
    ax[0].set_ylabel("Amplitude")
    ax[0].set_xlabel("Time [s]")
    ax[0].legend(loc="upper right")
    ax[0].grid(linestyle='--', alpha=0.5)
    ax[0].set_xlim(0.0, 0.5)

    # Plot frequency
    ax[1].set_title("Frequency Response")
    ax[1].semilogx(freqs, gain_db, color='black', linewidth=2)

    # Mark cutoff
    cutoff_freq = 1000
    cutoff_idx = np.abs(freqs - cutoff_freq).argmin()
    cutoff_db = gain_db[cutoff_idx]

    ax[1].axvline(cutoff_freq, color='black', linestyle='--', alpha=0.5, label=f"Cutoff {cutoff_freq}Hz")
    ax[1].axhline(-3, color='black', linestyle='-', alpha=0.5, label='-3dB')
    ax[1].plot(cutoff_freq, cutoff_db, 'ko')

    ax[1].set_ylabel("Magnitude [dB]")
    ax[1].set_xlabel("Frequency [Hz]")
    ax[1].set_ylim(-50, 5)
    ax[1].grid(linestyle='--', which='both', alpha=0.5)
    ax[1].legend(loc='upper right')

    fig.suptitle(f'{name.upper()} Response')
    plt.tight_layout()
    plt.savefig(f'../out/svf_{name}.png', dpi=400)
    print(f'Plotted {name}.')

def main():
    plot_response('../tmp/svf_out_lp.csv')
    plot_response('../tmp/svf_out_bp.csv')
    plot_response('../tmp/svf_out_hp.csv')
    plot_response('../tmp/svf_out_br.csv')
    print('Done...')

if __name__ == "__main__":
    main()