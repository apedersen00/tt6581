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

#include "sim_common.h"
#include "Vtb_svf.h"

#include <vector>

struct FilterMode {
    std::string name;
    int mode_bits;
    std::string filename;
};

// Run one sample through the filter state machine
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

int main(int argc, char** argv) {
    Verilated::mkdir("logs");
    const std::unique_ptr<VerilatedContext> contextp{new VerilatedContext};
    contextp->commandArgs(argc, argv);
    contextp->traceEverOn(false);
    const std::unique_ptr<Vtb_svf> top{new Vtb_svf{contextp.get(), "TOP"}};

    // Filter parameters
    double fc = 1000.0;
    double q  = 0.707;

    // Initial pin state
    top->clk_i     = 0;
    top->start_i   = 0;
    top->coeff_f_i = get_coeff_f(fc);
    top->coeff_q_i = get_coeff_q(q);

    // Sweep parameters
    double duration_sec = 2.0;
    int total_samples   = duration_sec * SAMPLE_RATE_HZ;
    double start_freq   = 20.0;
    double end_freq     = 20000.0;
    double amplitude    = 8191.0;

    std::vector<FilterMode> test_modes = {
        {"Lowpass",    0b001, "tmp/svf_out_lp.csv"},
        {"Bandpass",   0b010, "tmp/svf_out_bp.csv"},
        {"Highpass",   0b100, "tmp/svf_out_hp.csv"},
        {"Bandreject", 0b101, "tmp/svf_out_br.csv"}
    };

    std::cout << "[TB] SVF Filter Testbench" << std::endl;
    std::cout << "[TB] Cutoff: " << fc << " Hz, Q: " << q << std::endl;
    std::cout << "[TB] Sweep: " << start_freq << " Hz to " << end_freq
              << " Hz over " << duration_sec << " s" << std::endl;

    for (const auto& mode : test_modes) {
        std::cout << "\n[TB] Executing " << mode.name << " sweep..." << std::endl;

        std::ofstream output_file(mode.filename);
        if (!output_file.is_open()) {
            std::cerr << "[TB] Error: Could not open " << mode.filename << std::endl;
            return 1;
        }
        output_file << "time_sec,in_val,out_val,freq_hz\n";

        // Reset
        top->rst_ni     = 0;
        top->filt_sel_i = mode.mode_bits;
        for (int i = 0; i < 5; i++) tick(contextp, top);
        top->rst_ni = 1;
        for (int i = 0; i < 5; i++) tick(contextp, top);

        double phase = 0.0;

        for (int i = 0; i < total_samples; i++) {
            double t_sec = (double)i / SAMPLE_RATE_HZ;

            double current_freq = start_freq * std::pow(end_freq / start_freq, t_sec / duration_sec);

            phase += 2.0 * M_PI * current_freq / SAMPLE_RATE_HZ;
            if (phase > 2.0 * M_PI) phase -= 2.0 * M_PI;

            int16_t svf_input = (int16_t)(std::sin(phase) * amplitude);

            top->wave_i = svf_input & 0x3FFF;

            run_sample(contextp, top);

            int16_t out_val = (int16_t)(top->wave_o << 2) >> 2;

            output_file << t_sec << "," << svf_input << "," << out_val << "," << current_freq << "\n";
        }

        output_file.close();
        std::cout << "[TB] Saved to " << mode.filename << std::endl;
    }

    top->final();

    std::cout << "\n[TB] All simulations finished." << std::endl;
    return 0;
}
