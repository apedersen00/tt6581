//-------------------------------------------------------------------------------------------------
//
//  File: sim_envelope.cpp
//  Description: Verilator testbench for 8-bit envelope generator.
//               Inputs maximum amplitude and applies envelope.
//
//  Author:
//    - Andreas Pedersen
//
//-------------------------------------------------------------------------------------------------

#include "sim_common.h"
#include "Vtb_envelope.h"

const uint64_t MAX_CYCLES = 100000000;

int main(int argc, char** argv) {
    Verilated::mkdir("logs");
    const std::unique_ptr<VerilatedContext> contextp{new VerilatedContext};
    contextp->commandArgs(argc, argv);
    contextp->traceEverOn(false);
    const std::unique_ptr<Vtb_envelope> top{new Vtb_envelope{contextp.get(), "TOP"}};

    std::ofstream csv_file("tmp/envelope_output.csv");
    csv_file << "time_sec,voice_idx,gate,value\n";

    // Initial pin state
    top->clk_i       = 0;
    top->rst_ni      = 0;
    top->start_i     = 0;
    top->voice_i     = 511;  // Max positive signed 10-bit
    top->voice_idx_i = 0;
    top->gate_i      = 0;

    // Envelope settings
    top->attack_i  = 0xA;   // 100 ms
    top->decay_i   = 0x8;   // 300 ms
    top->sustain_i = 0xA;   // 0xAA/0xFF = ~0.66
    top->release_i = 0x9;   // 750 ms

    std::cout << "[TB] Envelope Generator Testbench" << std::endl;

    // Reset
    for (int i = 0; i < 5; i++) tick(contextp, top);
    top->rst_ni = 1;
    for (int i = 0; i < 5; i++) tick(contextp, top);

    uint64_t cycle_count  = 0;
    uint64_t sample_timer = 0;
    int current_voice = 0;
    int tdm_phase     = 0;

    while (cycle_count < MAX_CYCLES) {
        double time_now = cycle_count * 20e-9;

        // Apply gate
        if (time_now > 0.002 && time_now < 0.75) {
            top->gate_i = 1;
        } else {
            top->gate_i = 0;
        }

        sample_timer++;
        top->start_i = 0;

        switch (tdm_phase) {
            case 0:
                if (sample_timer >= CYCLES_PER_SAMPLE) {
                    sample_timer = 0;
                    current_voice = 0;
                    tdm_phase = 1;
                }
                break;

            case 1:
                top->voice_idx_i = current_voice;
                top->start_i = 1;
                tdm_phase = 2;
                break;

            case 2:
                if (top->ready_o) {
                    if (current_voice == 0) {
                        int64_t prod = (int64_t)top->prod_o;
                        csv_file << time_now << ","
                                 << current_voice << ","
                                 << (int)top->gate_i << ","
                                 << prod << "\n";
                    }

                    current_voice++;
                    if (current_voice < 3) {
                        tdm_phase = 1;
                    } else {
                        tdm_phase = 0;
                    }
                }
                break;
        }

        tick(contextp, top);
        cycle_count++;
    }

    csv_file.close();
    top->final();

    std::cout << "[TB] Simulation finished. Time simulated: "
              << cycle_count * 20e-9 << "s" << std::endl;
    return 0;
}
