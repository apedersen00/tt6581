//-------------------------------------------------------------------------------------------------
// File: sim_mult.cpp
// Description: Testbench for Shift-Add Multiplier
//-------------------------------------------------------------------------------------------------

#include <memory>
#include <iostream>
#include <cstdlib>
#include <cstdint>
#include <verilated.h>
#include "Vtb_mult.h"

void tick(const std::unique_ptr<VerilatedContext>& ctx,
          const std::unique_ptr<Vtb_mult>& top) {
    top->clk_i = 0;
    top->eval();
    ctx->timeInc(10);

    top->clk_i = 1;
    top->eval();
    ctx->timeInc(10);
}

// Sign-extend a 24-bit value to int32
int32_t sext24(uint32_t val) {
    if (val & 0x800000) return (int32_t)(val | 0xFF000000);
    return (int32_t)val;
}

// Sign-extend a 16-bit value to int32
int32_t sext16(uint16_t val) {
    return (int16_t)val;
}

int main(int argc, char** argv) {
    Verilated::mkdir("logs");
    const std::unique_ptr<VerilatedContext> contextp{new VerilatedContext};
    contextp->debug(0);
    contextp->traceEverOn(true);
    contextp->commandArgs(argc, argv);

    const std::unique_ptr<Vtb_mult> top{new Vtb_mult{contextp.get(), "TOP"}};

    top->clk_i   = 0;
    top->rst_ni  = 0;
    top->start_i = 0;
    top->op_a_i  = 0;
    top->op_b_i  = 0;

    for (int i = 0; i < 5; i++) tick(contextp, top);
    top->rst_ni = 1;
    tick(contextp, top);

    const int NUM_TESTS = 100;
    int pass_count = 0;
    int fail_count = 0;

    std::cout << "Starting Signed 24x16 Multiplier Verification (" << NUM_TESTS << " runs)..." << std::endl;

    struct TestCase { int32_t a; int16_t b; };
    TestCase fixed_tests[] = {
        {       0,      0 },
        {       1,      1 },
        {      -1,      1 },
        {       1,     -1 },
        {      -1,     -1 },
        { 8191,    255 },
        { 0x7FFFFF,  0x7FFF },
        {-0x800000,  0x7FFF },
        { 0x7FFFFF, -0x8000 },
        {-0x800000, -0x8000 },
    };
    int num_fixed = sizeof(fixed_tests) / sizeof(fixed_tests[0]);

    for (int i = 0; i < NUM_TESTS; i++) {
        int32_t in_a;
        int16_t in_b;

        if (i < num_fixed) {
            in_a = fixed_tests[i].a;
            in_b = fixed_tests[i].b;
        } else {
            in_a = (int32_t)((rand() & 0xFFFFFF) | ((rand() & 1) ? 0xFF000000 : 0)) ;
            in_a = sext24(in_a & 0xFFFFFF);
            in_b = (int16_t)(rand() & 0xFFFF);
        }

        top->op_a_i  = in_a & 0xFFFFFF;
        top->op_b_i  = in_b & 0xFFFF;
        top->start_i = 1;
        tick(contextp, top);

        top->start_i = 0;

        int cycles = 0;
        while (!top->ready_o && cycles < 30) {
            tick(contextp, top);
            cycles++;
        }

        int64_t expected = (int64_t)in_a * (int64_t)in_b;
        int64_t got      = (int64_t)top->prod_o;

        if (got & (1LL << 39)) got |= ~((1LL << 40) - 1);

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
    std::cout << "------------------------" << std::endl;
    std::cout << "Tests Passed: " << pass_count << std::endl;
    std::cout << "Tests Failed: " << fail_count << std::endl;

    return (fail_count == 0) ? 0 : 1;
}