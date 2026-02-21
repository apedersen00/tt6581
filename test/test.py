# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, FallingEdge, Timer

SPI_FREQ_NS = 200  # Half-period of SPI clock (keep well below 50 MHz sys clk)

async def spi_write(dut, addr: int, data: int):
    """Write an 8-bit value to a 7-bit register address over SPI.

    Drives ui_in[0] (sclk), ui_in[1] (cs), ui_in[2] (mosi).
    """
    # [1(write) | addr(7) | data(8)]
    word = (1 << 15) | ((addr & 0x7F) << 8) | (data & 0xFF)

    base = int(dut.ui_in.value) & ~0x07

    dut.ui_in.value = base | 0x00  # sclk=0, cs=0, mosi=0
    await Timer(SPI_FREQ_NS, unit="ns")

    # Shift out MSB first
    for i in range(15, -1, -1):
        bit = (word >> i) & 1
        # Drive MOSI, SCLK low
        dut.ui_in.value = base | (bit << 2) | 0x00  # cs=0, sclk=0
        await Timer(SPI_FREQ_NS, unit="ns")
        # Rising edge of SCLK
        dut.ui_in.value = base | (bit << 2) | 0x01  # cs=0, sclk=1
        await Timer(SPI_FREQ_NS, unit="ns")

    # SCLK back low
    dut.ui_in.value = base | 0x00
    await Timer(SPI_FREQ_NS, unit="ns")

    # Deassert CS (drive bit 1 high)
    dut.ui_in.value = base | 0x02  # cs=1
    await Timer(SPI_FREQ_NS, unit="ns")


async def spi_read(dut, addr: int) -> int:
    """Read an 8-bit value from a 7-bit register address over SPI.

    Returns the byte read back on MISO (uo_out[0]).
    """
    # Build the 16-bit word: [0(read) | addr(7) | 0x00(don't care)]
    word = (0 << 15) | ((addr & 0x7F) << 8) | 0x00

    base = int(dut.ui_in.value) & ~0x07

    # Assert CS
    dut.ui_in.value = base | 0x00
    await Timer(SPI_FREQ_NS, unit="ns")

    read_val = 0

    for i in range(15, -1, -1):
        bit = (word >> i) & 1
        # SCLK low, drive MOSI
        dut.ui_in.value = base | (bit << 2) | 0x00
        await Timer(SPI_FREQ_NS, unit="ns")
        # SCLK rising edge
        dut.ui_in.value = base | (bit << 2) | 0x01
        await Timer(SPI_FREQ_NS, unit="ns")

        # During the data phase (bits 7..0), sample MISO on falling edge
        if i <= 7:
            miso_bit = int(dut.uo_out.value) & 0x01
            read_val = (read_val << 1) | miso_bit

    # SCLK low, deassert CS
    dut.ui_in.value = base | 0x00
    await Timer(SPI_FREQ_NS, unit="ns")
    dut.ui_in.value = base | 0x02
    await Timer(SPI_FREQ_NS, unit="ns")

    return read_val

def get_audio_pre_ds(dut) -> int:
    """Return the signed 14-bit value feeding the delta-sigma modulator."""
    raw = dut.tt6581.tt6581_inst.mult_out.value
    # .value is a cocotb LogicArray — .to_signed() handles sign extension
    return raw.to_signed()


def get_bypass_accum(dut) -> int:
    """Return the 14-bit bypass (unfiltered) accumulator."""
    return dut.tt6581.tt6581_inst.bypass_accum.value.to_signed()


def get_filter_accum(dut) -> int:
    """Return the 14-bit filter accumulator."""
    return dut.tt6581.tt6581_inst.filter_accum.value.to_signed()

REG_V0_FREQ_LO  = 0x00
REG_V0_FREQ_HI  = 0x01
REG_V0_PW_LO    = 0x02
REG_V0_PW_HI    = 0x03
REG_V0_CONTROL  = 0x04
REG_V0_AD       = 0x05
REG_V0_SR       = 0x06
REG_FILT_VOLUME = 0x1A

@cocotb.test()
async def test_project(dut):
    dut._log.info("Start")

    # 50 MHz system clock
    clock = Clock(dut.clk, 20, unit="ns")
    cocotb.start_soon(clock.start())

    # ── Reset ──
    dut._log.info("Reset")
    dut.ena.value = 1
    dut.ui_in.value = 0x02   # cs=1 (deasserted), sclk=0, mosi=0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 10)

    # ── Configure voice 0 via SPI ──
    dut._log.info("Configuring voice 0 via SPI")

    # Set frequency (16-bit freq word = 0x1CD8 ≈ 440 Hz equivalent)
    await spi_write(dut, REG_V0_FREQ_LO, 0xD8)
    await spi_write(dut, REG_V0_FREQ_HI, 0x1C)

    # Set pulse width for pulse wave (not needed for saw, but good to set)
    await spi_write(dut, REG_V0_PW_LO, 0x00)
    await spi_write(dut, REG_V0_PW_HI, 0x08)  # 50% duty cycle

    # Set envelope: fast attack (0), mid decay (6), sustain=F, mid release (6)
    await spi_write(dut, REG_V0_AD, 0x06)      # attack=0, decay=6
    await spi_write(dut, REG_V0_SR, 0xF6)      # sustain=F, release=6

    # Set master volume
    await spi_write(dut, REG_FILT_VOLUME, 0xFF)

    # Set control: sawtooth wave (0010) + gate on (bit 0)
    # control[7:4]=wave_sel, [2]=ring_mod, [1]=sync, [0]=gate
    await spi_write(dut, REG_V0_CONTROL, 0x21)  # saw + gate

    dut._log.info("Voice 0 configured, waiting for audio output...")

    for i in range(20):
        await ClockCycles(dut.clk, 1000)

        audio_val = get_audio_pre_ds(dut)
        bypass_val = get_bypass_accum(dut)
        dut._log.info(
            f"Sample {i:2d}: mult_out={audio_val:6d}  "
            f"bypass_accum={bypass_val:6d}"
        )
