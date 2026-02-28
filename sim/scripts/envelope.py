"""
Parses envelope testbench output.
"""

import pandas as pd
import matplotlib.pyplot as plt

def main():
    df = pd.read_csv('../tmp/envelope_output.csv')

    # prod_o = voice_signed * env_raw (0-255)
    # To get envelope-scaled voice: divide by 255
    # Result is in voice units: -512 to +511
    df['scaled_voice'] = df['value'] / 255

    # Plot
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(df['time_sec'], df['scaled_voice'], linewidth=2, color='black', label='Envelope')
    ax.plot(df['time_sec'], df['gate'] * 511, linewidth=2, color='blue', label='Gate', linestyle='--', alpha=0.5)

    adsr = (
        "A: 0xA (500 ms)\n"
        "D: 0x8 (300 ms)\n"
        "S: 0xA (~0.67) \n"
        "R: 0x9 (750 ms)"
    )

    ax.plot([], [], ' ', label=adsr)

    ax.set_title('ADSR Envelope')
    ax.set_xlabel('Time [s]')
    ax.set_ylabel('Amplitude')
    ax.legend(loc='upper right')
    ax.grid(linestyle='--', alpha=0.5)
    ax.set_xlim(0, 1.5)
    plt.savefig('../out/envelope.png', dpi=400)
    print('Done...')

if __name__ == "__main__":
    main()