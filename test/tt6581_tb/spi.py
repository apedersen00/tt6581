"""
SPI driver for the TT6581 register interface.
"""

from cocotb.triggers import Timer

from .constants import SPI_FREQ_NS

async def spi_write(dut, addr: int, data: int):
    """
    Write an 8-bit value to a 7-bit register address over SPI.
    Frame: [1(write) | addr(7) | data(8)], MSB first.

    Pin mapping (uio_in):
        [0] CS
        [1] MOSI
        [3] SCK
    """
    word = (1 << 15) | ((addr & 0x7F) << 8) | (data & 0xFF)

    # Assert CS (low)
    dut.uio_in.value = 0x00  # cs=0, mosi=0, sclk=0
    await Timer(SPI_FREQ_NS, unit="ns")

    # Shift out MSB first
    for i in range(15, -1, -1):
        bit = (word >> i) & 1
        dut.uio_in.value = (bit << 1)         # cs=0, mosi=bit, sclk=0
        await Timer(SPI_FREQ_NS, unit="ns")
        dut.uio_in.value = (bit << 1) | 0x08  # cs=0, mosi=bit, sclk=1
        await Timer(SPI_FREQ_NS, unit="ns")

    # SCLK back low
    dut.uio_in.value = 0x00
    await Timer(SPI_FREQ_NS, unit="ns")

    # Deassert CS (high)
    dut.uio_in.value = 0x01
    await Timer(SPI_FREQ_NS, unit="ns")


async def spi_read(dut, addr: int) -> int:
    """
    Read an 8-bit value from a 7-bit register address over SPI.
    Frame: [0(read) | addr(7) | 0x00], MSB first.

    MISO is read from uio_out[2].
    """
    word = ((addr & 0x7F) << 8) | 0x00

    dut.uio_in.value = 0x00  # CS low
    await Timer(SPI_FREQ_NS, unit="ns")

    read_val = 0
    for i in range(15, -1, -1):
        bit = (word >> i) & 1
        dut.uio_in.value = (bit << 1)         # cs=0, mosi=bit, sclk=0
        await Timer(SPI_FREQ_NS, unit="ns")
        dut.uio_in.value = (bit << 1) | 0x08  # cs=0, mosi=bit, sclk=1
        await Timer(SPI_FREQ_NS, unit="ns")
        if i <= 7:
            miso_bit = (int(dut.uio_out.value) >> 2) & 0x01
            read_val = (read_val << 1) | miso_bit

    dut.uio_in.value = 0x00
    await Timer(SPI_FREQ_NS, unit="ns")
    dut.uio_in.value = 0x01  # CS high
    await Timer(SPI_FREQ_NS, unit="ns")

    return read_val
