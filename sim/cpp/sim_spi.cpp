//-------------------------------------------------------------------------------------------------
//
//  File: sim_spi.cpp
//  Description: Verilator testbench for register SPI interface.
//               Reads and writes test values and checks the reg_file interface.
//
//  Author:
//    - Andreas Pedersen
//
//-------------------------------------------------------------------------------------------------

#include "sim_common.h"
#include "Vtb_spi.h"

const int SPI_CLK_DIV = 20;  // SPI clock = SysClk / 20 = 2.5 MHz

uint8_t spi_bit(const std::unique_ptr<VerilatedContext>& ctx,
                const std::unique_ptr<Vtb_spi>& top,
                uint8_t bit_out) {
    uint8_t bit_in = 0;
    top->mosi_i = bit_out & 1;

    for (int i = 0; i < SPI_CLK_DIV / 2; i++) tick(ctx, top);

    top->sclk_i = 1;

    for (int i = 0; i < SPI_CLK_DIV / 2; i++) tick(ctx, top);

    top->sclk_i = 0;
    bit_in = top->miso_o;

    return bit_in;
}

uint8_t spi_byte(const std::unique_ptr<VerilatedContext>& ctx,
                 const std::unique_ptr<Vtb_spi>& top,
                 uint8_t data_out) {
    uint8_t data_in = 0;
    // MSB First
    for (int i = 7; i >= 0; i--) {
        uint8_t bit_val = (data_out >> i) & 1;
        uint8_t miso_bit = spi_bit(ctx, top, bit_val);
        if (miso_bit) {
            data_in |= (1 << i);
        }
    }
    return data_in;
}

void check_write(const std::unique_ptr<VerilatedContext>& ctx,
                 const std::unique_ptr<Vtb_spi>& top,
                 uint8_t addr, uint8_t data) {
    std::cout << "[Write] Addr: 0x" << std::hex << (int)addr
              << " Data: 0x" << (int)data << std::dec << " ... ";

    top->cs_i = 0;

    uint8_t cmd = 0x80 | (addr & 0x7F);
    spi_byte(ctx, top, cmd);
    spi_byte(ctx, top, data);

    for (int i = 0; i < 5; i++) tick(ctx, top);
    top->cs_i = 1;
    for (int i = 0; i < 5; i++) tick(ctx, top);

    if (top->reg_addr_o == addr && top->reg_wdata_o == data) {
        std::cout << "PASS" << std::endl;
    } else {
        std::cout << "FAIL (Got Addr: " << (int)top->reg_addr_o
                  << " Data: " << (int)top->reg_wdata_o << ")" << std::endl;
    }
}

void check_read(const std::unique_ptr<VerilatedContext>& ctx,
                const std::unique_ptr<Vtb_spi>& top,
                uint8_t addr, uint8_t expected_val) {
    std::cout << "[Read ] Addr: 0x" << std::hex << (int)addr << std::dec << " ... ";

    top->reg_rdata_i = expected_val;
    top->cs_i = 0;

    uint8_t cmd = 0x00 | (addr & 0x7F);
    spi_byte(ctx, top, cmd);

    uint8_t result = spi_byte(ctx, top, 0x00);

    for (int i = 0; i < 5; i++) tick(ctx, top);
    top->cs_i = 1;
    for (int i = 0; i < 5; i++) tick(ctx, top);

    if (result == expected_val) {
        std::cout << "PASS" << std::endl;
    } else {
        std::cout << "FAIL (Expected: " << (int)expected_val
                  << " Got: " << (int)result << ")" << std::endl;
    }
}

int main(int argc, char** argv) {
    Verilated::mkdir("logs");
    const std::unique_ptr<VerilatedContext> contextp{new VerilatedContext};
    contextp->commandArgs(argc, argv);
    contextp->traceEverOn(false);
    const std::unique_ptr<Vtb_spi> top{new Vtb_spi{contextp.get(), "TOP"}};

    // Initial pin state
    top->clk_i       = 0;
    top->rst_ni      = 0;
    top->sclk_i      = 0;
    top->cs_i        = 1;
    top->mosi_i      = 0;
    top->reg_rdata_i = 0;

    std::cout << "[TB] SPI Interface Testbench" << std::endl;

    // Reset
    for (int i = 0; i < 5; i++) tick(contextp, top);
    top->rst_ni = 1;
    for (int i = 0; i < 5; i++) tick(contextp, top);

    check_write(contextp, top, 0x02, 0xFF);
    check_write(contextp, top, 0x05, 0xAA);
    check_read(contextp, top, 0x02, 0x55);
    check_read(contextp, top, 0x05, 0x99);

    for (int i = 0; i < 50; i++) tick(contextp, top);

    top->final();

    std::cout << "[TB] Simulation finished." << std::endl;
    return 0;
}
