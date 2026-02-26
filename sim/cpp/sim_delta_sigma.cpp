#include <memory>
#include <iostream>
#include <fstream>
#include <cmath>
#include <verilated.h>
#include "Vtb_delta_sigma.h"

const uint64_t CLK_FREQ_HZ = 50000000;      // 50 MHz System Clock
const uint64_t AUDIO_RATE_HZ = 50000;       // 50 kHz Audio Rate
const uint64_t DAC_RATE_HZ = 10000000;      // 10 MHz DAC Rate
const uint64_t CYCLES_PER_AUDIO = CLK_FREQ_HZ / AUDIO_RATE_HZ; // 1000 cycles
const uint64_t CYCLES_PER_DAC = CLK_FREQ_HZ / DAC_RATE_HZ;     // 5 cycles

// Coherent Sampling Setup
const uint64_t FFT_SAMPLES = 1048576; // 2^20 samples for the FFT
const int TARGET_FREQ = 1000;
// Force a prime number of cycles fitting exactly into the FFT window
const int PRIME_CYCLES = 103; 
const double ACTUAL_FREQ = (double)PRIME_CYCLES * DAC_RATE_HZ / FFT_SAMPLES;

void tick(const std::unique_ptr<VerilatedContext>& ctx,
          const std::unique_ptr<Vtb_delta_sigma>& top) {
    top->clk_i = 0;
    top->eval();
    ctx->timeInc(10); // 10ns
    top->clk_i = 1;
    top->eval();
    ctx->timeInc(10); // 10ns
}

int main(int argc, char** argv) {
    Verilated::mkdir("logs");
    const std::unique_ptr<VerilatedContext> contextp{new VerilatedContext};
    contextp->debug(0);
    contextp->traceEverOn(false);
    contextp->commandArgs(argc, argv);

    const std::unique_ptr<Vtb_delta_sigma> top{new Vtb_delta_sigma{contextp.get(), "TOP"}};

    // We will just dump a single column of 0s and 1s to keep file I/O fast
    std::ofstream out_file;
    out_file.open("pdm_output.txt");

    top->clk_i = 0;
    top->rst_ni = 0;
    top->audio_valid_i = 0;
    top->audio_i = 0;

    uint64_t cycle_count = 0;
    uint64_t dac_samples_captured = 0;
    double time_now = 0.0;

    std::cout << "Starting Simulation..." << std::endl;
    std::cout << "Coherent Test Freq: " << ACTUAL_FREQ << " Hz" << std::endl;

    while (dac_samples_captured < FFT_SAMPLES && !contextp->gotFinish()) {
        
        // 1. Reset Handling
        if (cycle_count < 20) {
            top->rst_ni = 0;
        } else {
            top->rst_ni = 1;
        }

        if (top->rst_ni) {
            time_now = (cycle_count - 20) / (double)CLK_FREQ_HZ;

            // 2. Drive Audio Input at 50 kHz
            if ((cycle_count - 20) % CYCLES_PER_AUDIO == 0) {
                top->audio_valid_i = 1;
                // Generate a 14-bit sine wave (amplitude 8000 out of 8191 to prevent clipping)
                int16_t sine_val = (int16_t)(8000.0 * sin(2.0 * M_PI * ACTUAL_FREQ * time_now));
                top->audio_i = sine_val;
            } else {
                top->audio_valid_i = 0;
            }

            // 3. Capture 1-bit DAC output at 10 MHz
            // The DAC logic updates exactly 1 cycle after ce_10m goes high.
            // Sampling it every 5 system cycles correctly captures the 10 MHz stream.
            if ((cycle_count - 20) % CYCLES_PER_DAC == 0) {
                out_file << (int)top->wave_o << "\n";
                dac_samples_captured++;
                
                if (dac_samples_captured % 262144 == 0) {
                    std::cout << "Captured " << dac_samples_captured << " / " << FFT_SAMPLES << " samples..." << std::endl;
                }
            }
        }

        tick(contextp, top);
        cycle_count++;
    }

    out_file.close();
    top->final();
    contextp->statsPrintSummary();
    std::cout << "Simulation finished. Output saved to pdm_output.txt" << std::endl;
    return 0;
}