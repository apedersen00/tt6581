//-------------------------------------------------------------------------------------------------
//
//  File: sim_mult.cpp
//  Description: Verilator testbench for 24x16 bit shift-add multiplier.
//               Inputs N random values and verifies them against software results.
//
//  Author:
//    - Andreas Pedersen
//
//-------------------------------------------------------------------------------------------------

#include "sim_common.h"
#include "Vtb_mult.h"

#include <cstdlib>

// Sign-extend a 24-bit value to int32
int32_t sext24(uint32_t val) {
    if (val & 0x800000) return (int32_t)(val | 0xFF000000);
    return (int32_t)val;
}

// Sign-extend a 16-bit value to int32
int32_t sext16(uint16_t val) {
    return (int16_t)val;
}

const int NUM_TESTS = 10000;

int main(int argc, char** argv) {
    Verilated::mkdir("logs");
    const std::unique_ptr<VerilatedContext> contextp{new VerilatedContext};
    contextp->commandArgs(argc, argv);
    contextp->traceEverOn(false);
    const std::unique_ptr<Vtb_mult> top{new Vtb_mult{contextp.get(), "TOP"}};

    // Initial pin state
    top->clk_i   = 0;
    top->rst_ni  = 0;
    top->start_i = 0;
    top->op_a_i  = 0;
    top->op_b_i  = 0;

    std::cout << "[TB] Signed 24x16 Multiplier Testbench (" << NUM_TESTS << " tests)" << std::endl;

    // Reset
    for (int i = 0; i < 5; i++) tick(contextp, top);
    top->rst_ni = 1;
    for (int i = 0; i < 5; i++) tick(contextp, top);

    int pass_count = 0;
    int fail_count = 0;

    for (int i = 0; i < NUM_TESTS; i++) {
        // Generate random input values
        int32_t in_a = (int32_t)((rand() & 0xFFFFFF) | ((rand() & 1) ? 0xFF000000 : 0));
        in_a = sext24(in_a & 0xFFFFFF);
        int16_t in_b = (int16_t)(rand() & 0xFFFF);

        // Start multiplier
        top->op_a_i  = in_a & 0xFFFFFF;
        top->op_b_i  = in_b & 0xFFFF;
        top->start_i = 1;
        tick(contextp, top);
        top->start_i = 0;

        // Wait for completion
        int cycles = 0;
        while (!top->ready_o && cycles < 30) {
            tick(contextp, top);
            cycles++;
        }

        // Check against software result
        int64_t expected = (int64_t)in_a * (int64_t)in_b;
        int64_t got      = (int64_t)top->prod_o;

        if (got & (1LL << 39)) {
            got |= ~((1LL << 40) - 1);
        }

        if (got == expected) {
            pass_count++;
            std::cout << "[PASS] Iter: " << i
                      << "\tA: " << in_a << "\tB: " << (int)in_b
                      << "\t| Exp: " << expected
                      << "\t| Got: " << got << std::endl;
        } else {
            fail_count++;
            std::cout << "[FAIL] Iter: " << i
                      << "\tA: " << in_a << "\tB: " << (int)in_b
                      << "\t| Exp: " << expected
                      << "\t| Got: " << got << std::endl;
        }

        tick(contextp, top);
    }

    top->final();

    std::cout << "\n[TB] Tests Passed: " << pass_count << std::endl;
    std::cout << "[TB] Tests Failed: " << fail_count << std::endl;
    return 0;
}
