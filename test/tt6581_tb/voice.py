# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

"""Voice and filter programming helpers."""

from .constants import (
    REG_FREQ_LO, REG_FREQ_HI, REG_PW_LO, REG_PW_HI,
    REG_CTRL, REG_AD, REG_SR,
    REG_FILT_F_LO, REG_FILT_F_HI, REG_FILT_Q_LO, REG_FILT_Q_HI,
    REG_FILT_ENMOD, REG_FILT_VOL,
    calc_fcw, get_coeff_f, get_coeff_q,
)
from .spi import spi_write


# =============================================================================
#  Voice programming helpers
# =============================================================================

async def set_voice_freq(dut, voice_base: int, freq_hz: float):
    """Program the frequency control word for a voice."""
    fcw = calc_fcw(freq_hz)
    await spi_write(dut, voice_base + REG_FREQ_LO, fcw & 0xFF)
    await spi_write(dut, voice_base + REG_FREQ_HI, (fcw >> 8) & 0xFF)


async def set_voice_pw(dut, voice_base: int, pw: int):
    """Program the 12-bit pulse width for a voice (0x000 – 0xFFF)."""
    await spi_write(dut, voice_base + REG_PW_LO, pw & 0xFF)
    await spi_write(dut, voice_base + REG_PW_HI, (pw >> 8) & 0x0F)


async def set_voice_adsr(dut, voice_base: int,
                         attack: int, decay: int,
                         sustain: int, release: int):
    """Program attack/decay/sustain/release (4-bit each) for a voice."""
    ad = ((attack & 0x0F) << 4) | (decay & 0x0F)
    sr = ((sustain & 0x0F) << 4) | (release & 0x0F)
    await spi_write(dut, voice_base + REG_AD, ad)
    await spi_write(dut, voice_base + REG_SR, sr)


async def set_voice_control(dut, voice_base: int,
                            waveform: int, gate: bool,
                            ring_mod: bool = False, sync: bool = False):
    """Program the voice control register.

    waveform: WAVE_TRI / WAVE_SAW / WAVE_PULSE / WAVE_NOISE (or OR-ed combo)
    gate:     True = start envelope attack, False = release
    """
    ctrl = waveform & 0xFE
    if gate:
        ctrl |= 0x01
    if sync:
        ctrl |= 0x02
    if ring_mod:
        ctrl |= 0x04
    await spi_write(dut, voice_base + REG_CTRL, ctrl)


async def setup_voice(dut, voice_base: int, freq_hz: float,
                      waveform: int, pw: int = 0x800,
                      attack: int = 0, decay: int = 6,
                      sustain: int = 0xF, release: int = 6):
    """Convenience: fully configure a voice (freq + PW + ADSR) in one call.

    Does NOT gate the voice — call set_voice_control() afterwards.
    """
    await set_voice_freq(dut, voice_base, freq_hz)
    await set_voice_pw(dut, voice_base, pw)
    await set_voice_adsr(dut, voice_base, attack, decay, sustain, release)


async def gate_on(dut, voice_base: int, waveform: int,
                  ring_mod: bool = False, sync: bool = False):
    """Open the gate (start attack phase)."""
    await set_voice_control(dut, voice_base, waveform, gate=True,
                            ring_mod=ring_mod, sync=sync)


async def gate_off(dut, voice_base: int, waveform: int):
    """Close the gate (start release phase)."""
    await set_voice_control(dut, voice_base, waveform, gate=False)


# =============================================================================
#  Filter programming helpers
# =============================================================================

async def set_filter(dut, fc_hz: float, q: float, en_mode: int):
    """Program the filter cutoff, resonance and routing/mode register.

    fc_hz:   cutoff frequency in Hz
    q:       resonance Q factor (≥ 0.5 typ.)
    en_mode: OR of FILT_V0/V1/V2 (voice routing) | FILT_LP/BP/HP (mode)
    """
    cf = get_coeff_f(fc_hz)
    cq = get_coeff_q(q)
    await spi_write(dut, REG_FILT_F_LO, cf & 0xFF)
    await spi_write(dut, REG_FILT_F_HI, (cf >> 8) & 0xFF)
    await spi_write(dut, REG_FILT_Q_LO, cq & 0xFF)
    await spi_write(dut, REG_FILT_Q_HI, (cq >> 8) & 0xFF)
    await spi_write(dut, REG_FILT_ENMOD, en_mode)


async def set_filter_cutoff(dut, fc_hz: float):
    """Update only the filter cutoff frequency."""
    cf = get_coeff_f(fc_hz)
    await spi_write(dut, REG_FILT_F_LO, cf & 0xFF)
    await spi_write(dut, REG_FILT_F_HI, (cf >> 8) & 0xFF)


async def set_filter_q(dut, q: float):
    """Update only the filter resonance."""
    cq = get_coeff_q(q)
    await spi_write(dut, REG_FILT_Q_LO, cq & 0xFF)
    await spi_write(dut, REG_FILT_Q_HI, (cq >> 8) & 0xFF)


async def set_volume(dut, vol: int):
    """Set the master volume register (0x00 – 0xFF)."""
    await spi_write(dut, REG_FILT_VOL, vol & 0xFF)
