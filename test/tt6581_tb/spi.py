# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

"""Low-level SPI driver for the TT6581 register interface."""

from cocotb.triggers import Timer

from .constants import SPI_FREQ_NS


async def spi_write(dut, addr: int, data: int):
    """Write an 8-bit value to a 7-bit register address over SPI.

    Frame: [1(write) | addr(7) | data(8)], MSB first.
    Drives ui_in[0] (sclk), ui_in[1] (cs), ui_in[2] (mosi).
    """
    word = (1 << 15) | ((addr & 0x7F) << 8) | (data & 0xFF)
    base = int(dut.ui_in.value) & ~0x07

    # Assert CS (low)
    dut.ui_in.value = base | 0x00
    await Timer(SPI_FREQ_NS, unit="ns")

    # Shift out MSB first
    for i in range(15, -1, -1):
        bit = (word >> i) & 1
        dut.ui_in.value = base | (bit << 2) | 0x00   # cs=0, sclk=0
        await Timer(SPI_FREQ_NS, unit="ns")
        dut.ui_in.value = base | (bit << 2) | 0x01   # cs=0, sclk=1
        await Timer(SPI_FREQ_NS, unit="ns")

    # SCLK back low
    dut.ui_in.value = base | 0x00
    await Timer(SPI_FREQ_NS, unit="ns")

    # Deassert CS (high)
    dut.ui_in.value = base | 0x02
    await Timer(SPI_FREQ_NS, unit="ns")


async def spi_read(dut, addr: int) -> int:
    """Read an 8-bit value from a 7-bit register address over SPI.

    Frame: [0(read) | addr(7) | 0x00], MSB first.
    Returns the byte sampled on uo_out[0] (MISO) during the data phase.
    """
    word = ((addr & 0x7F) << 8) | 0x00
    base = int(dut.ui_in.value) & ~0x07

    dut.ui_in.value = base | 0x00
    await Timer(SPI_FREQ_NS, unit="ns")

    read_val = 0
    for i in range(15, -1, -1):
        bit = (word >> i) & 1
        dut.ui_in.value = base | (bit << 2) | 0x00
        await Timer(SPI_FREQ_NS, unit="ns")
        dut.ui_in.value = base | (bit << 2) | 0x01
        await Timer(SPI_FREQ_NS, unit="ns")
        if i <= 7:
            miso_bit = int(dut.uo_out.value) & 0x01
            read_val = (read_val << 1) | miso_bit

    dut.ui_in.value = base | 0x00
    await Timer(SPI_FREQ_NS, unit="ns")
    dut.ui_in.value = base | 0x02
    await Timer(SPI_FREQ_NS, unit="ns")

    return read_val
