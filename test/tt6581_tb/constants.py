# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

"""Register map, waveform masks, filter bits, note frequencies and global config."""

import math
import os

# =============================================================================
#  Output directory
# =============================================================================

TB_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test", "tmp")
# Resolve robustly: test/tt6581_tb/../tmp → test/tmp
TB_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "tmp")
TB_OUTPUT_DIR = os.path.normpath(TB_OUTPUT_DIR)
os.makedirs(TB_OUTPUT_DIR, exist_ok=True)

# =============================================================================
#  Clocking
# =============================================================================

SPI_FREQ_NS = 200          # Half-period of SPI clock (well below 50 MHz sys clk)
SYS_CLK_HZ  = 50_000_000
SAMPLE_RATE  = 50_000      # Internal sample rate driven by tick_gen

# =============================================================================
#  Per-voice register offsets (relative to voice base)
# =============================================================================

REG_FREQ_LO = 0x00
REG_FREQ_HI = 0x01
REG_PW_LO   = 0x02
REG_PW_HI   = 0x03
REG_CTRL    = 0x04
REG_AD      = 0x05
REG_SR      = 0x06

# =============================================================================
#  Voice base addresses
# =============================================================================

V0_BASE = 0x00
V1_BASE = 0x07
V2_BASE = 0x0E

# =============================================================================
#  Filter registers (absolute addresses)
# =============================================================================

FILT_BASE      = 0x15
REG_FILT_F_LO  = FILT_BASE + 0x00   # 0x15
REG_FILT_F_HI  = FILT_BASE + 0x01   # 0x16
REG_FILT_Q_LO  = FILT_BASE + 0x02   # 0x17
REG_FILT_Q_HI  = FILT_BASE + 0x03   # 0x18
REG_FILT_ENMOD = FILT_BASE + 0x04   # 0x19
REG_FILT_VOL   = FILT_BASE + 0x05   # 0x1A

# =============================================================================
#  Waveform select masks (upper nibble of CTRL register)
# =============================================================================

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

# =============================================================================
#  Filter mode bits (EN_MODE[2:0])
# =============================================================================

FILT_LP = 0x01
FILT_BP = 0x02
FILT_HP = 0x04

# =============================================================================
#  Voice filter-enable bits (EN_MODE[5:3])
# =============================================================================

FILT_V0 = 0x08
FILT_V1 = 0x10
FILT_V2 = 0x20

# =============================================================================
#  Note frequencies (Hz)
# =============================================================================

NOTE_FREQ = {
    "C2": 65.41,  "D2": 73.42,  "Eb2": 77.78,  "F2": 87.31,
    "G2": 98.00,  "Ab2": 103.83, "Bb2": 116.54, "B2": 123.47,
    "C3": 130.81, "D3": 146.83, "Eb3": 155.56, "F3": 174.61,
    "G3": 196.00, "Ab3": 207.65, "Bb3": 233.08, "B3": 246.94,
    "C4": 261.63, "D4": 293.66, "Eb4": 311.13, "F4": 349.23,
    "G4": 392.00, "Ab4": 415.30, "Bb4": 466.16, "B4": 493.88,
    "C5": 523.25, "D5": 587.33, "Eb5": 622.25, "G5": 783.99,
}

# =============================================================================
#  Coefficient helpers
# =============================================================================

def calc_fcw(freq_hz: float) -> int:
    """Compute the 16-bit frequency control word.

    FCW = freq * 2^19 / 50000   (matches Verilator testbench)
    """
    return int(freq_hz * (1 << 19) / SAMPLE_RATE)


def get_coeff_f(fc_hz: float) -> int:
    """Compute the signed 16-bit (Q1.15) filter cutoff coefficient.

    f = 2 * sin(pi * fc / Fs)  scaled to Q1.15
    """
    f = 2.0 * math.sin(math.pi * fc_hz / SAMPLE_RATE)
    val = int(f * 32768.0)
    val = max(-32768, min(32767, val))
    return val & 0xFFFF


def get_coeff_q(q: float) -> int:
    """Compute the signed 16-bit (Q4.12) filter resonance (damping) coefficient.

    q_damp = 1/Q  scaled to Q4.12
    """
    q_damp = 1.0 / q
    val = int(q_damp * 4096.0)
    val = max(-32768, min(32767, val))
    return val & 0xFFFF
