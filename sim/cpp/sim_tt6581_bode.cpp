//-------------------------------------------------------------------------------------------------
//
//  File: sim_tt6581_bode.cpp
//  Description: Verilator testbench for TT6581.
//               Plays a stepped frequency sweep (20 Hz-20 kHz) through Voice 0
//               with a 1 kHz LP filter applied and captures the PDM output.
//
//  Author:
//    - Andreas Pedersen
//
//-------------------------------------------------------------------------------------------------

#include "sim_common.h"
#include "Vtb_tt6581_bode.h"

int main(int argc, char** argv) {
    Verilated::mkdir("logs");
    const std::unique_ptr<VerilatedContext> contextp{new VerilatedContext};
    contextp->commandArgs(argc, argv);
    contextp->traceEverOn(false);
    const std::unique_ptr<Vtb_tt6581_bode> top{new Vtb_tt6581_bode{contextp.get(), "TOP"}};

    PdmCapture pdm;
    uint64_t tick_count = 0;

    auto sys_tick = [&]() {
        tick(contextp, top);
        tick_count++;
        if (pdm.active && (tick_count % CYCLES_PER_DAC == 0)) {
            pdm.capture(top->wave_o);
        }
    };

    auto sys_tick_batch = [&](uint64_t n) {
        for (uint64_t i = 0; i < n; i++) sys_tick();
    };

    // Sweep parameters
    const double START_FREQ      = 20.0;
    const double END_FREQ        = 6250.0;
    const int    NUM_STEPS       = 200;
    const int    CYCLES_PER_STEP = 20;

    std::cout << "[TB] TT6581 Frequency Response" << std::endl;
    std::cout << "[TB] Sweep: " << START_FREQ << " Hz - " << END_FREQ << " Hz, "
              << NUM_STEPS << " steps, " << CYCLES_PER_STEP << " cycles each" << std::endl;

    // Initial pin state
    top->clk_i  = 0;
    top->rst_ni = 0;
    top->sclk_i = 0;
    top->cs_i   = 1;
    top->mosi_i = 0;

    // Reset
    for (int i = 0; i < 5; i++) sys_tick();
    top->rst_ni = 1;
    for (int i = 0; i < 5; i++) sys_tick();

    // Configure voice 0
    set_voice_freq(top, sys_tick, V1_BASE, START_FREQ);
    spi_write(top, sys_tick, V1_BASE + REG_PW_LO, 0x00);
    spi_write(top, sys_tick, V1_BASE + REG_PW_HI, 0x08);
    spi_write(top, sys_tick, V1_BASE + REG_AD, 0x00);
    spi_write(top, sys_tick, V1_BASE + REG_SR, 0xF0);
    spi_write(top, sys_tick, V1_BASE + REG_CTRL, WAVE_TRI | 0x01);

    // Configure filter
    double fc = 1000.0;
    double Q  = 0.707;

    int16_t fc_i = get_coeff_f(fc);
    int16_t Q_i  = get_coeff_q(Q);

    spi_write(top, sys_tick, FILT_BASE + REG_F_LO, (fc_i >> 0) & 0xFF);
    spi_write(top, sys_tick, FILT_BASE + REG_F_HI, (fc_i >> 8) & 0xFF);
    spi_write(top, sys_tick, FILT_BASE + REG_Q_LO, (Q_i >> 0) & 0xFF);
    spi_write(top, sys_tick, FILT_BASE + REG_Q_HI, (Q_i >> 8) & 0xFF);
    spi_write(top, sys_tick, FILT_BASE + REG_EN_MODE, 0b00001001);  // LP, Voice 0 routed
    spi_write(top, sys_tick, FILT_BASE + REG_VOLUME, 0xFF);

    // Open output files
    pdm.open("tmp/bode.bin");
    std::ofstream csv("tmp/bode.csv");
    csv << "time_sec,freq_hz\n";

    tick_count = 0;
    pdm.active = true;

    // Settle
    int settle_samples = (int)(0.05 * SAMPLE_RATE_HZ);
    for (int i = 0; i < settle_samples; i++) {
        sys_tick_batch(CYCLES_PER_SAMPLE);
    }

    double t_sec = 0.0;

    // Sweep
    for (int step = 0; step < NUM_STEPS; step++) {
        double frac = (double)step / (NUM_STEPS - 1);
        double freq = START_FREQ * std::pow(END_FREQ / START_FREQ, frac);

        set_voice_freq(top, sys_tick, V1_BASE, freq);

        double dwell_sec    = CYCLES_PER_STEP / freq;
        int    dwell_samples = std::max(1, (int)(dwell_sec * SAMPLE_RATE_HZ));

        for (int s = 0; s < dwell_samples; s++) {
            sys_tick_batch(CYCLES_PER_SAMPLE);
            csv << t_sec << "," << freq << "\n";
            t_sec += 1.0 / SAMPLE_RATE_HZ;
        }

        if (step % 10 == 0) {
            std::cout << "[TB] Step " << step << "/" << NUM_STEPS
                      << " (" << (int)freq << " Hz, "
                      << dwell_samples << " samples)" << std::endl;
        }
    }

    pdm.flush();
    csv.close();
    top->final();

    std::cout << "\n[TB] PDM samples: " << pdm.total
              << " (" << (double)pdm.total / DAC_RATE_HZ << "s)" << std::endl;
    return 0;
}
