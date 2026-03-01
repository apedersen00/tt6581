//-------------------------------------------------------------------------------------------------
//
//  File: sim_delta_sigma.cpp
//  Description: Verilator testbench for the delta-sigma modulator.
//               Inputs a 1 kHz sine wave and captures the 1-bit PDM output.
//
//  Author:
//    - Andreas Pedersen
//
//-------------------------------------------------------------------------------------------------

#include "sim_common.h"
#include "Vtb_delta_sigma.h"

const double   TONE_FREQ       = 1000.0;                            // 1 kHz test tone
const int16_t  AMPLITUDE       = 1024;
const uint64_t NUM_DAC_SAMPLES = 1 << 20;                           // ~0.1 s at 10 MHz
const double   DURATION_SEC    = (double)NUM_DAC_SAMPLES / DAC_RATE_HZ;

int main(int argc, char** argv) {
    Verilated::mkdir("logs");
    const std::unique_ptr<VerilatedContext> contextp{new VerilatedContext};
    contextp->commandArgs(argc, argv);
    contextp->traceEverOn(false);
    const std::unique_ptr<Vtb_delta_sigma> top{new Vtb_delta_sigma{contextp.get(), "TOP"}};

    PdmCapture pdm;
    pdm.open("tmp/delta_sigma.bin");

    // Initial pin state
    top->clk_i         = 0;
    top->rst_ni        = 0;
    top->audio_valid_i = 0;
    top->audio_i       = 0;

    std::cout << "[TB] Delta-Sigma Modulator Testbench" << std::endl;
    std::cout << "[TB] Tone: " << TONE_FREQ << " Hz, Amplitude: " << AMPLITUDE
              << " (max 2048), Duration: " << DURATION_SEC << " s" << std::endl;

    // Reset
    for (int i = 0; i < 5; i++) tick(contextp, top);
    top->rst_ni = 1;
    for (int i = 0; i < 5; i++) tick(contextp, top);

    uint64_t cycle = 0;

    while (pdm.total < NUM_DAC_SAMPLES) {
        double t = (double)cycle / CLK_FREQ_HZ;

        // Drive audio input at sample rate
        if (cycle % CYCLES_PER_SAMPLE == 0) {
            top->audio_valid_i = 1;
            top->audio_i = (int16_t)(AMPLITUDE * sin(2.0 * M_PI * TONE_FREQ * t));
        } else {
            top->audio_valid_i = 0;
        }

        // Capture PDM at DAC rate
        if (cycle % CYCLES_PER_DAC == 0) {
            pdm.capture(top->wave_o);
        }

        tick(contextp, top);
        cycle++;
    }

    pdm.flush();
    top->final();

    std::cout << "[TB] Captured " << pdm.total << " PDM samples" << std::endl;
    return 0;
}
