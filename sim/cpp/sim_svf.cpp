//-------------------------------------------------------------------------------------------------
// File: sim_svf.cpp
// Description: Verilator testbench for sequential SVF filter with shared multiplier
//-------------------------------------------------------------------------------------------------

#include <memory>
#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <string>
#include <cmath>
#include <verilated.h>
#include "Vtb_svf.h"

const double Fs = 50000.0;          // Sample Rate

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

    // One extra tick to latch outputs if needed
    tick(ctx, top);
}

int main(int argc, char** argv) {
    Verilated::mkdir("logs");
    const std::unique_ptr<VerilatedContext> contextp{new VerilatedContext};
    contextp->commandArgs(argc, argv);
    const std::unique_ptr<Vtb_svf> top{new Vtb_svf{contextp.get(), "TOP"}};

    // 1. Open Input CSV
    std::ifstream input_file("../data/10s_nocturne.csv");
    if (!input_file.is_open()) {
        std::cerr << "Error: Could not open input.csv" << std::endl;
        return 1;
    }

    std::ofstream output_file("svf_out.csv");
    output_file << "time_sec,output_val\n"; 

    // 3. Configure Filter
    double fc = 3000.0;      // Cutoff: 2 kHz
    double q  = 0.707;       // Butterworth
    int mode  = 0b001;       // 001: LP, 010: BP, 100: HP

    top->clk_i      = 0;
    top->rst_ni     = 0;
    top->start_i    = 0;
    top->filt_sel_i = mode; 
    top->coeff_f_i  = get_coeff_f(fc);
    top->coeff_q_i  = get_coeff_q(q);

    // Reset sequence
    for (int i = 0; i < 10; i++) tick(contextp, top);
    top->rst_ni = 1;
    tick(contextp, top);

    std::cout << "[Sim] Processing CSV data..." << std::endl;
    std::cout << "      Cutoff: " << fc << " Hz, Q: " << q << std::endl;

    std::string line;
    std::getline(input_file, line); 

    int sample_count = 0;

    // 4. Processing Loop
    while (std::getline(input_file, line)) {
        std::stringstream ss(line);
        std::string txt_time, txt_val;
        
        if (std::getline(ss, txt_time, ',') && std::getline(ss, txt_val, ',')) {
            double t_sec = std::stod(txt_time);
            double in_raw = std::stod(txt_val);

            int16_t svf_input = (int16_t)((in_raw - 512.0) * 16.0);

            top->wave_i = svf_input;

            run_sample(contextp, top);

            output_file << t_sec << "," << (int)top->wave_o << "\n";
            
            sample_count++;
        }
    }

    std::cout << "[Sim] Done! Processed " << sample_count << " samples." << std::endl;
    std::cout << "[Sim] Output saved to 'output.csv'" << std::endl;

    input_file.close();
    output_file.close();
    top->final();
    return 0;
}