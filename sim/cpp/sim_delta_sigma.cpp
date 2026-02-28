//-------------------------------------------------------------------------------------------------
//
//  File: sim_delta_sigma.cpp
//  Description: Verilator testbench for the delta-sigma modulator.
//               Feeds a 1 kHz sine wave at maximum amplitude and captures
//               the 1-bit PDM output.
//
//  Author:
//    - Andreas Pedersen
//
//-------------------------------------------------------------------------------------------------

#include <memory>
#include <iostream>
#include <fstream>
#include <cmath>
#include <verilated.h>
#include "Vtb_delta_sigma.h"

const uint64_t CLK_FREQ_HZ      = 50000000;                        // 50 MHz
const uint64_t AUDIO_RATE_HZ    = 50000;                            // 50 kHz
const uint64_t DAC_RATE_HZ      = 10000000;                         // 10 MHz
const uint64_t CYCLES_PER_AUDIO = CLK_FREQ_HZ / AUDIO_RATE_HZ;     // 1000
const uint64_t CYCLES_PER_DAC   = CLK_FREQ_HZ / DAC_RATE_HZ;       // 5

const double   TONE_FREQ        = 1000.0;                           // 1 kHz test tone
const int16_t  AMPLITUDE        = 1024;
const uint64_t NUM_DAC_SAMPLES  = 1 << 20;                          // ~0.1 s at 10 MHz
const double   DURATION_SEC     = (double)NUM_DAC_SAMPLES / DAC_RATE_HZ;

void tick(const std::unique_ptr<VerilatedContext>& ctx,
          const std::unique_ptr<Vtb_delta_sigma>& top) {
    top->clk_i = 0;
    top->eval();
    ctx->timeInc(10);
    top->clk_i = 1;
    top->eval();
    ctx->timeInc(10);
}

int main(int argc, char** argv) {
    Verilated::mkdir("logs");
    const std::unique_ptr<VerilatedContext> contextp{new VerilatedContext};
    contextp->traceEverOn(false);
    contextp->commandArgs(argc, argv);
    const std::unique_ptr<Vtb_delta_sigma> top{new Vtb_delta_sigma{contextp.get(), "TOP"}};

    std::ofstream pdm_file("tmp/delta_sigma.bin", std::ios::binary);

    top->clk_i = 0;
    top->rst_ni = 0;
    top->audio_valid_i = 0;
    top->audio_i = 0;

    std::cout << "[TB] Delta-Sigma Modulator Testbench" << std::endl;
    std::cout << "[TB] Tone: " << TONE_FREQ << " Hz, Amplitude: " << AMPLITUDE
              << " (max 2048), Duration: " << DURATION_SEC << " s" << std::endl;

    // Reset
    for (int i = 0; i < 20; i++) tick(contextp, top);
    top->rst_ni = 1;
    for (int i = 0; i < 5; i++) tick(contextp, top);

    uint64_t cycle    = 0;
    uint64_t captured = 0;
    uint8_t  pdm_byte = 0;
    int      bit_count = 0;

    while (captured < NUM_DAC_SAMPLES) {
        double t = (double)cycle / CLK_FREQ_HZ;

        // Drive audio input at 50 kHz
        if (cycle % CYCLES_PER_AUDIO == 0) {
            top->audio_valid_i = 1;
            top->audio_i = (int16_t)(AMPLITUDE * sin(2.0 * M_PI * TONE_FREQ * t));
        } else {
            top->audio_valid_i = 0;
        }

        // Capture PDM at 10 MHz, pack into bytes
        if (cycle % CYCLES_PER_DAC == 0) {
            pdm_byte = (pdm_byte << 1) | (top->wave_o & 1);
            bit_count++;
            if (bit_count == 8) {
                pdm_file.put(static_cast<char>(pdm_byte));
                pdm_byte  = 0;
                bit_count = 0;
            }
            captured++;
        }

        tick(contextp, top);
        cycle++;
    }

    // Flush remaining bits
    if (bit_count > 0) {
        pdm_byte <<= (8 - bit_count);
        pdm_file.put(static_cast<char>(pdm_byte));
    }

    pdm_file.close();
    top->final();

    std::cout << "[TB] Captured " << captured << " PDM samples" << std::endl;
    return 0;
}