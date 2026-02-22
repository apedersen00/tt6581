# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

"""RTL signal accessors, reset helper, and reusable audio capture routine."""

from cocotb.triggers import ClockCycles, RisingEdge


# =============================================================================
#  Signal accessors — read internal RTL signals
# =============================================================================

def _sid(dut):
    """Shortcut to the tt6581 instance inside the TT wrapper."""
    return dut.tt6581.tt6581_inst


def get_audio_pre_ds(dut) -> int:
    """Return the signed 14-bit value feeding the delta-sigma modulator (mult_out)."""
    return _sid(dut).mult_out.value.to_signed()


def get_bypass_accum(dut) -> int:
    """Return the signed 14-bit bypass (unfiltered) accumulator."""
    return _sid(dut).bypass_accum.value.to_signed()


def get_filter_accum(dut) -> int:
    """Return the signed 14-bit filter accumulator."""
    return _sid(dut).filter_accum.value.to_signed()


def get_audio_valid(dut) -> bool:
    """Return True when audio_valid is asserted (new sample ready)."""
    return bool(_sid(dut).audio_valid.value)


def get_ds_audio_i(dut) -> int:
    """Return the signed 14-bit audio_i inside the delta-sigma module."""
    return _sid(dut).delta_sigma_inst.audio_i.value.to_signed()


def get_ds_audio_valid(dut) -> bool:
    """Return the audio_valid_i flag inside the delta-sigma module."""
    return bool(_sid(dut).delta_sigma_inst.audio_valid_i.value)


def get_wave_o(dut) -> int:
    """Return the 1-bit PDM output."""
    return int(_sid(dut).delta_sigma_inst.wave_o.value)


# =============================================================================
#  Reset helper
# =============================================================================

async def reset_dut(dut, cycles: int = 10):
    """Assert reset for *cycles* clocks, then deassert and settle."""
    dut.ena.value = 1
    dut.ui_in.value = 0x02   # cs=1 (deasserted), sclk=0, mosi=0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, cycles)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, cycles)


# =============================================================================
#  Reusable capture routine
# =============================================================================

async def capture_audio(dut, num_samples: int = 500,
                        max_clocks: int = 2_000_000,
                        log_every: int = 100) -> list[int]:
    """Capture *num_samples* of delta-sigma audio_i (on audio_valid_i pulses).

    Returns a list of signed 14-bit integers.
    """
    audio_samples: list[int] = []

    for _ in range(max_clocks):
        await RisingEdge(dut.clk)

        if get_ds_audio_valid(dut):
            audio_val = get_ds_audio_i(dut)
            audio_samples.append(audio_val)

            if log_every and (len(audio_samples) % log_every == 0
                              or len(audio_samples) <= 3):
                dut._log.info(
                    f"[sample {len(audio_samples):4d}] "
                    f"audio_i = {audio_val:6d}"
                )
            if len(audio_samples) >= num_samples:
                break

    return audio_samples
