"""
Voice and filter programming helpers.
"""

from .constants import (
    REG_FREQ_LO, REG_FREQ_HI, REG_PW_LO, REG_PW_HI,
    REG_CTRL, REG_AD, REG_SR,
    REG_FILT_F_LO, REG_FILT_F_HI, REG_FILT_Q_LO, REG_FILT_Q_HI,
    REG_FILT_ENMOD, REG_FILT_VOL,
    calc_fcw, get_coeff_f, get_coeff_q,
)
from .spi import spi_write

#==================================
# Voice functions
#==================================
async def set_voice_freq(dut, voice_base: int, freq_hz: float):
    """
    Program the frequency control word for a voice.
    """
    fcw = calc_fcw(freq_hz)
    await spi_write(dut, voice_base + REG_FREQ_LO, fcw & 0xFF)
    await spi_write(dut, voice_base + REG_FREQ_HI, (fcw >> 8) & 0xFF)

async def set_voice_pw(dut, voice_base: int, pw: int):
    """
    Program the 12-bit pulse width for a voice.
    """
    await spi_write(dut, voice_base + REG_PW_LO, pw & 0xFF)
    await spi_write(dut, voice_base + REG_PW_HI, (pw >> 8) & 0x0F)

async def set_voice_adsr(dut, voice_base: int,
                         attack: int, decay: int,
                         sustain: int, release: int):
    """
    Program attack/decay/sustain/release (4-bit each) for a voice.
    """
    ad = ((attack & 0x0F) << 4) | (decay & 0x0F)
    sr = ((sustain & 0x0F) << 4) | (release & 0x0F)
    await spi_write(dut, voice_base + REG_AD, ad)
    await spi_write(dut, voice_base + REG_SR, sr)

async def set_voice_control(dut, voice_base: int,
                            waveform: int, gate: bool,
                            ring_mod: bool = False, sync: bool = False):
    """
    Program the voice control register.

    waveform: WAVE_TRI / WAVE_SAW / WAVE_PULSE / WAVE_NOISE
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
    """
    Configure a voice (freq + PW + ADSR).
    """
    await set_voice_freq(dut, voice_base, freq_hz)
    await set_voice_pw(dut, voice_base, pw)
    await set_voice_adsr(dut, voice_base, attack, decay, sustain, release)

async def gate_on(dut, voice_base: int, waveform: int,
                  ring_mod: bool = False, sync: bool = False):
    """
    Open the gate (start attack phase).
    """
    await set_voice_control(dut, voice_base, waveform, gate=True,
                            ring_mod=ring_mod, sync=sync)

async def gate_off(dut, voice_base: int, waveform: int):
    """
    Close the gate (start release phase).
    """
    await set_voice_control(dut, voice_base, waveform, gate=False)

async def set_volume(dut, vol: int):
    """
    Set the volume register.
    """
    await spi_write(dut, REG_FILT_VOL, vol & 0xFF)
