"""
Register map, waveform masks, filter bits, note frequencies and global config.
"""

import math
import os

#==================================
# Output
#==================================
TB_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test", "tmp")
TB_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "tmp")
TB_OUTPUT_DIR = os.path.normpath(TB_OUTPUT_DIR)
os.makedirs(TB_OUTPUT_DIR, exist_ok=True)

#==================================
# Clocking
#==================================
SPI_FREQ_NS = 200           # SPI clock frequency
SYS_CLK_HZ  = 50_000_000    # System clock frequency
SAMPLE_RATE  = 50_000       # Sample rate driven by tick_gen

# Delta-sigma parameters
PDM_CLK_DIV = 5                             # Delta-Sigma clock = 50/5 = 10 MHz
PDM_RATE    = SYS_CLK_HZ // PDM_CLK_DIV     # 10 MHz
FILT_ORDER  = 4                             # Butterworth filter order
FILT_CUTOFF = 20_000                        # Output low-pass cutoff

#==================================
# Voice register offset
#==================================
REG_FREQ_LO = 0x00
REG_FREQ_HI = 0x01
REG_PW_LO   = 0x02
REG_PW_HI   = 0x03
REG_CTRL    = 0x04
REG_AD      = 0x05
REG_SR      = 0x06

#==================================
# Voice base addresses
#==================================
V0_BASE = 0x00
V1_BASE = 0x07
V2_BASE = 0x0E

#==================================
# Filter addresses
#==================================
FILT_BASE      = 0x15
REG_FILT_F_LO  = FILT_BASE + 0x00   # 0x15
REG_FILT_F_HI  = FILT_BASE + 0x01   # 0x16
REG_FILT_Q_LO  = FILT_BASE + 0x02   # 0x17
REG_FILT_Q_HI  = FILT_BASE + 0x03   # 0x18
REG_FILT_ENMOD = FILT_BASE + 0x04   # 0x19
REG_FILT_VOL   = FILT_BASE + 0x05   # 0x1A

#==================================
# Waveform bit masks
#==================================
WAVE_TRI   = 0x10
WAVE_SAW   = 0x20
WAVE_PULSE = 0x40
WAVE_NOISE = 0x80

WAVEFORM_NAMES = {
    WAVE_TRI:   "Triangle",
    WAVE_SAW:   "Sawtooth",
    WAVE_PULSE: "Pulse",
    WAVE_NOISE: "Noise",
}

#==================================
# Filter mode bits
#==================================
FILT_LP = 0x01
FILT_BP = 0x02
FILT_HP = 0x04
FILT_BR = 0x05  # Band-reject (LP | HP)

FILTER_MODE_NAMES = {
    FILT_LP: "LP",
    FILT_BP: "BP",
    FILT_HP: "HP",
    FILT_BR: "BR",
}

#==================================
# Filter enable bits
#==================================
FILT_V0 = 0x08
FILT_V1 = 0x10
FILT_V2 = 0x20

#==================================
# Functions
#==================================
def calc_fcw(freq_hz: float) -> int:
    """
    Compute the 16-bit frequency control word.
    FCW = freq * 2^19 / 50000
    """
    return int(freq_hz * (1 << 19) / SAMPLE_RATE)

def get_coeff_f(fc_hz: float) -> int:
    """
    Compute the signed 16-bit (Q1.15) filter cutoff coefficient.
    f = 2 * sin(pi * fc / Fs)
    """
    f = 2.0 * math.sin(math.pi * fc_hz / SAMPLE_RATE)
    val = int(f * 32768.0)
    val = max(-32768, min(32767, val))
    return val & 0xFFFF

def get_coeff_q(q: float) -> int:
    """
    Compute the signed 16-bit (Q4.12) filter damping coefficient (Q).
    q_damp = 1/Q  scaled to Q4.12
    """
    q_damp = 1.0 / q
    val = int(q_damp * 4096.0)
    val = max(-32768, min(32767, val))
    return val & 0xFFFF
