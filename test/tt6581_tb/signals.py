"""
PDM audio capture.
"""

import numpy as np
from scipy.signal import butter, sosfilt
from cocotb.triggers import ClockCycles

from .constants import (
    PDM_CLK_DIV, PDM_RATE, FILT_ORDER, FILT_CUTOFF, SAMPLE_RATE,
)

#==================================
# TT6581 reset
#==================================
async def reset_dut(dut, cycles: int = 10):
    """Assert reset for *cycles* clocks, then deassert and settle."""
    dut.ena.value = 1
    dut.ui_in.value = 0x00
    dut.uio_in.value = 0x01  # cs=1 (deasserted), sclk=0, mosi=0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, cycles)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, cycles)


#==================================
# Delta-Sigma capture
#==================================
async def capture_audio(dut, num_samples: int = 500,
                        log_every: int = 100) -> list[float]:
    """
    Capture audio by sampling the 1-bit PDM output and reconstructing
    the analog waveform with a 4th order Butterworth low-pass filter.
    """
    decimation = PDM_RATE // SAMPLE_RATE
    num_pdm    = num_samples * decimation
    pdm_bits   = np.empty(num_pdm, dtype=np.float32)

    for i in range(num_pdm):
        await ClockCycles(dut.clk, PDM_CLK_DIV)
        try:
            pdm_bits[i] = 1.0 if str(dut.uo_out.value)[-1] == '1' else 0.0
        except (ValueError, IndexError):
            pdm_bits[i] = 0.0

        if log_every and (i + 1) % (log_every * decimation) == 0:
            n = (i + 1) // decimation
            dut._log.info(f"[PDM] {n}/{num_samples} audio samples captured")

    pdm_bits = pdm_bits * 2.0 - 1.0

    sos = butter(FILT_ORDER, FILT_CUTOFF, btype='low', fs=PDM_RATE, output='sos')
    filtered = sosfilt(sos, pdm_bits)

    # Downsample: PDM_RATE -> SAMPLE_RATE
    audio = filtered[::decimation]

    return audio.tolist()
