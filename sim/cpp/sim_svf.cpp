//-------------------------------------------------------------------------------------------------
//
//  File: sim_svf.cpp
//  Description: Verilator testbench for Chamberlin State-Variable filter.
//               Inputs a sine sweep and logs output for all 4 filter modes.
//
//  Author:
//    - Andreas Pedersen
//
//-------------------------------------------------------------------------------------------------

#include <memory>
#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <cmath>
#include <verilated.h>
#include "Vtb_svf.h"

const double Fs = 50000.0;

void tick(const std::unique_ptr<VerilatedContext>& ctx,
          const std::unique_ptr<Vtb_svf>& top) {
    top->clk_i = 0;
    top->eval();
    ctx->timeInc(1);

    top->clk_i = 1;
    top->eval();
    ctx->timeInc(1);
}

// Q1.15 Coeff Calculation
int16_t get_coeff_f(double fc) {
    double f = 2.0 * std::sin(M_PI * fc / Fs);
    return (int16_t)(f * 32768.0);
}

// Q4.12 Coeff Calculation
int16_t get_coeff_q(double q) {
    double q_damp = 1.0 / q;
    return (int16_t)(q_damp * 4096.0);
}

// Run one sample through the state machine
void run_sample(const std::unique_ptr<VerilatedContext>& ctx,
                const std::unique_ptr<Vtb_svf>& top) {
    top->start_i = 1;
    tick(ctx, top);
    top->start_i = 0;

    int cycles = 0;
    while (!top->ready_o && cycles < 200) {
        tick(ctx, top);
        cycles++;
    }

    tick(ctx, top);
}

struct FilterMode {
    std::string name;
    int mode_bits;
    std::string filename;
};

int main(int argc, char** argv) {
    // Verilator init
    Verilated::mkdir("logs");
    const std::unique_ptr<VerilatedContext> contextp{new VerilatedContext};
    contextp->debug(0);
    contextp->traceEverOn(false);
    contextp->commandArgs(argc, argv);
    const std::unique_ptr<Vtb_svf> top{new Vtb_svf{contextp.get(), "TOP"}};

    // Configure Filter Params
    double fc = 1000.0;
    double q  = 0.707;
    top->clk_i     = 0;
    top->start_i   = 0;
    top->coeff_f_i = get_coeff_f(fc);
    top->coeff_q_i = get_coeff_q(q);

    // Sweep Parameters
    double duration_sec = 2.0;
    int total_samples = duration_sec * Fs;
    double start_freq = 20.0;
    double end_freq = 20000.0;
    double amplitude = 8191.0;

    std::vector<FilterMode> test_modes = {
        {"Lowpass",    0b001, "tmp/svf_out_lp.csv"},
        {"Bandpass",   0b010, "tmp/svf_out_bp.csv"},
        {"Highpass",   0b100, "tmp/svf_out_hp.csv"},
        {"Bandreject", 0b101, "tmp/svf_out_br.csv"}
    };

    std::cout << "[TB] Starting SVF testbench..." << std::endl;
    std::cout << "Cutoff: " << fc << " Hz, Q: " << q << std::endl;
    std::cout << "Sweep:  " << start_freq << "Hz to " << end_freq << "Hz over " << duration_sec << "s\n" << std::endl;

    for (const auto& mode : test_modes) {
        std::cout << "[TB] Executing " << mode.name << " sweep..." << std::endl;

        // Open CSV for this specific mode
        std::ofstream output_file(mode.filename);
        if (!output_file.is_open()) {
            std::cerr << "Error: Could not open " << mode.filename << std::endl;
            return 1;
        }
        output_file << "time_sec,in_val,out_val,freq_hz\n";

        // Reset
        top->rst_ni = 0;
        top->filt_sel_i = mode.mode_bits;
        for (int i = 0; i < 5; i++) tick(contextp, top);
        
        top->rst_ni = 1;
        for (int i = 0; i < 5; i++) tick(contextp, top);


        double phase = 0.0;

        // Sweep
        for (int i = 0; i < total_samples; i++) {
            double t_sec = (double)i / Fs;

            double current_freq = start_freq * std::pow(end_freq / start_freq, t_sec / duration_sec);

            phase += 2.0 * M_PI * current_freq / Fs;
            if (phase > 2.0 * M_PI) {
                phase -= 2.0 * M_PI;
            }

            double in_val_raw = std::sin(phase) * amplitude;
            int16_t svf_input = (int16_t)in_val_raw;

            top->wave_i = svf_input & 0x3FFF;

            run_sample(contextp, top);

            int16_t out_val = (int16_t)(top->wave_o << 2) >> 2;

            output_file << t_sec << "," << svf_input << "," << out_val << "," << current_freq << "\n";
        }

        output_file.close();
        std::cout << "[TB] Saved to " << mode.filename << "\n" << std::endl;
    }

    std::cout << "[TB] All simulations finished." << std::endl;
    top->final();
    return 0;
}
