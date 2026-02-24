# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

"""PDM audio capture and reset helper.

All signal reads use top-level ports (``uo_out``, ``ui_in``, etc.) so the
testbench runs identically on RTL and gate-level netlists.
"""

import numpy as np
from scipy.signal import butter, sosfilt
from cocotb.triggers import ClockCycles

from .constants import (
    PDM_CLK_DIV, PDM_RATE, FILT_ORDER, FILT_CUTOFF, SAMPLE_RATE,
)


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
#  PDM audio capture with Butterworth reconstruction
# =============================================================================

async def capture_audio(dut, num_samples: int = 500,
                        log_every: int = 100) -> list[float]:
    """
    Capture audio by sampling the 1-bit PDM output on ``uo_out[1]`` and
    reconstructing the analog waveform with a Butterworth low-pass filter.

    This mirrors the real-world reconstruction path (analog RC / active
    filter on the PCB recovering audio from the delta-sigma bitstream).

    Parameters
    ----------
    dut
        Cocotb DUT handle.
    num_samples : int
        Number of *audio-rate* samples to return (at ``SAMPLE_RATE``).
    log_every : int
        Log progress every *log_every* audio-rate samples (0 to disable).

    Returns
    -------
    list[float]
        Reconstructed audio samples (roughly +/-1.0 full-scale).
    """
    decimation = PDM_RATE // SAMPLE_RATE          # 200
    num_pdm    = num_samples * decimation
    pdm_bits   = np.empty(num_pdm, dtype=np.float32)

    x_count = 0
    for i in range(num_pdm):
        await ClockCycles(dut.clk, PDM_CLK_DIV)
        try:
            val = dut.uo_out.value
            pdm_bits[i] = 1.0 if val.binstr[-2] == '1' else 0.0
            if i < 20:
                dut._log.info(f"[PDM DBG] cycle {i}: uo_out={val.binstr} bit1={val.binstr[-2]}")
        except Exception as e:
            if x_count < 5:
                dut._log.warning(f"[PDM DBG] cycle {i}: exception reading uo_out: {e}")
            x_count += 1
            pdm_bits[i] = 0.0

        if log_every and (i + 1) % (log_every * decimation) == 0:
            n = (i + 1) // decimation
            dut._log.info(f"[PDM] {n}/{num_samples} audio samples captured")

    # {0, 1} -> {-1, +1}
    pdm_bits = pdm_bits * 2.0 - 1.0

    # Butterworth low-pass filter (SOS form for numerical stability)
    sos = butter(FILT_ORDER, FILT_CUTOFF, btype='low', fs=PDM_RATE, output='sos')
    filtered = sosfilt(sos, pdm_bits)

    # Downsample: PDM_RATE -> SAMPLE_RATE
    audio = filtered[::decimation]

    return audio.tolist()
