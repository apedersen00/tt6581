//-------------------------------------------------------------------------------------------------
//
//  File: sim_tt6581_bode.cpp
//  Description: Verilator testbench for TT6581.
//               Plays a stepped frequency sweep (20 Hz–20 kHz) through Voice 0
//               with a 1 kHz LP filter applied and captures the PDM output.
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
#include "Vtb_tt6581_bode.h"

#define CLK_PERIOD_NS 20   // 50 MHz System Clock
#define SPI_CLK_DIV   20   // SPI is 20x slower than SysClk (2.5 MHz)

const int CYCLES_PER_DAC = 5;         // 50 MHz / 10 MHz
const int PDM_RATE_HZ    = 10000000;  // 10 MHz DAC rate
const double Fs = 50000.0;

#ifndef M_PI
#    define M_PI 3.14159265358979323846
#endif

static std::ofstream g_pdm_file;
static uint8_t  g_pdm_byte      = 0;
static int      g_pdm_bit_count = 0;
static uint64_t g_pdm_total     = 0;
static uint64_t g_tick_count    = 0;
static bool     g_pdm_active    = false;

const uint8_t V1_BASE = 0x00;

const uint8_t REG_FREQ_LO = 0x00;
const uint8_t REG_FREQ_HI = 0x01;
const uint8_t REG_PW_LO   = 0x02;
const uint8_t REG_PW_HI   = 0x03;
const uint8_t REG_CTRL    = 0x04;
const uint8_t REG_AD      = 0x05;
const uint8_t REG_SR      = 0x06;

const uint8_t FILT_BASE   = 0x15;
const uint8_t REG_F_LO    = 0x00;
const uint8_t REG_F_HI    = 0x01;
const uint8_t REG_Q_LO    = 0x02;
const uint8_t REG_Q_HI    = 0x03;
const uint8_t REG_EN_MODE = 0x04;
const uint8_t REG_VOLUME  = 0x05;

const uint8_t WAVE_TRI = 0x10;

void sys_tick(const std::unique_ptr<VerilatedContext>& ctx,
              const std::unique_ptr<Vtb_tt6581_bode>& top) {
    top->clk_i = 0;
    top->eval();
    ctx->timeInc(CLK_PERIOD_NS / 2);

    top->clk_i = 1;
    top->eval();
    ctx->timeInc(CLK_PERIOD_NS / 2);

    if (g_pdm_active && (g_tick_count % CYCLES_PER_DAC == 0)) {
        g_pdm_byte = (g_pdm_byte << 1) | (top->wave_o & 1);
        g_pdm_bit_count++;
        if (g_pdm_bit_count == 8) {
            g_pdm_file.put(static_cast<char>(g_pdm_byte));
            g_pdm_byte = 0;
            g_pdm_bit_count = 0;
        }
        g_pdm_total++;
    }
    g_tick_count++;
}

void tick_batch(const std::unique_ptr<VerilatedContext>& ctx,
                const std::unique_ptr<Vtb_tt6581_bode>& top,
                int ticks) {
    for (int i = 0; i < ticks; i++) sys_tick(ctx, top);
}

void spi_write(const std::unique_ptr<VerilatedContext>& ctx,
               const std::unique_ptr<Vtb_tt6581_bode>& top,
               uint8_t addr, uint8_t data) {
    uint16_t frame = 0x8000 | (addr << 8) | data;
    top->cs_i = 0;
    for (int i = 15; i >= 0; i--) {
        top->mosi_i = (frame >> i) & 1;
        for (int k = 0; k < SPI_CLK_DIV / 2; k++) sys_tick(ctx, top);
        top->sclk_i = 1;
        for (int k = 0; k < SPI_CLK_DIV / 2; k++) sys_tick(ctx, top);
        top->sclk_i = 0;
    }
    for (int k = 0; k < SPI_CLK_DIV / 2; k++) sys_tick(ctx, top);
    top->cs_i = 1;
    for (int k = 0; k < 20; k++) sys_tick(ctx, top);
}

uint16_t calc_fcw(double freq) {
    uint64_t numerator = (uint64_t)freq * (1ULL << 19);
    return (uint16_t)(numerator / 50000ULL);
}

void set_voice_freq(const std::unique_ptr<VerilatedContext>& ctx,
                    const std::unique_ptr<Vtb_tt6581_bode>& top,
                    uint8_t base_addr, double freq) {
    uint16_t fcw = calc_fcw(freq);
    spi_write(ctx, top, base_addr + REG_FREQ_LO, fcw & 0xFF);
    spi_write(ctx, top, base_addr + REG_FREQ_HI, (fcw >> 8) & 0xFF);
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

int main(int argc, char** argv) {
    Verilated::mkdir("logs");
    const std::unique_ptr<VerilatedContext> contextp{new VerilatedContext};
    contextp->commandArgs(argc, argv);
    contextp->traceEverOn(false);
    const std::unique_ptr<Vtb_tt6581_bode> top{new Vtb_tt6581_bode{contextp.get(), "TOP"}};

    // Sweep parameters
    const int    SAMPLE_RATE      = 50000;                     // internal audio rate
    const int    TICKS_PER_SAMPLE = 50000000 / SAMPLE_RATE;    // 1000
    const double START_FREQ       = 20.0;
    const double END_FREQ         = 6250.0;
    const int    NUM_STEPS        = 200;                       // frequency steps
    const int    CYCLES_PER_STEP  = 20;                        // waveform cycles per step

    std::cout << "[TB] TT6581 Frequency Response" << std::endl;
    std::cout << "[TB] Sweep: " << START_FREQ << " Hz - " << END_FREQ << " Hz, "
              << NUM_STEPS << " steps, " << CYCLES_PER_STEP << " cycles each" << std::endl;

    // Reset
    top->clk_i  = 0;
    top->rst_ni = 0;
    top->sclk_i = 0;
    top->cs_i   = 1;
    top->mosi_i = 0;
    for (int i = 0; i < 5; i++) {
        sys_tick(contextp, top);
    }
    top->rst_ni = 1;
    for (int i = 0; i < 5; i++) {
        sys_tick(contextp, top);
    }

    // Configure voice 0
    set_voice_freq(contextp, top, V1_BASE, START_FREQ);
    spi_write(contextp, top, V1_BASE + REG_PW_LO, 0x00);
    spi_write(contextp, top, V1_BASE + REG_PW_HI, 0x08);
    spi_write(contextp, top, V1_BASE + REG_AD, 0x00);
    spi_write(contextp, top, V1_BASE + REG_SR, 0xF0);
    spi_write(contextp, top, V1_BASE + REG_CTRL, WAVE_TRI | 0x01); 

    double fc = 1000.0;
    double Q  = 0.707;

    int fc_i = get_coeff_f(fc);
    int Q_i = get_coeff_q(Q);

    spi_write(contextp, top, FILT_BASE + REG_F_LO, (fc_i >> 0) & 0xFF);
    spi_write(contextp, top, FILT_BASE + REG_F_HI, (fc_i >> 8) & 0xFF);
    spi_write(contextp, top, FILT_BASE + REG_Q_LO, (Q_i >> 0) & 0xFF);
    spi_write(contextp, top, FILT_BASE + REG_Q_HI, (Q_i >> 8) & 0xFF);
    spi_write(contextp, top, FILT_BASE + REG_EN_MODE, 0b00001001);  // LP, Voice 0 routed
    spi_write(contextp, top, FILT_BASE + REG_VOLUME, 0xFF);

    // Open output files
    g_pdm_file.open("tmp/bode.bin", std::ios::binary);
    std::ofstream csv("tmp/bode.csv");
    csv << "time_sec,freq_hz\n";

    g_pdm_byte      = 0;
    g_pdm_bit_count  = 0;
    g_pdm_total      = 0;
    g_tick_count     = 0;
    g_pdm_active     = true;

    int settle_samples = (int)(0.05 * SAMPLE_RATE);
    for (int i = 0; i < settle_samples; i++) {
        tick_batch(contextp, top, TICKS_PER_SAMPLE);
    }

    double t_sec = 0.0;

    for (int step = 0; step < NUM_STEPS; step++) {
        double frac = (double)step / (NUM_STEPS - 1);
        double freq = START_FREQ * std::pow(END_FREQ / START_FREQ, frac);

        set_voice_freq(contextp, top, V1_BASE, freq);

        double dwell_sec = CYCLES_PER_STEP / freq;
        int dwell_samples = std::max(1, (int)(dwell_sec * SAMPLE_RATE));

        for (int s = 0; s < dwell_samples; s++) {
            tick_batch(contextp, top, TICKS_PER_SAMPLE);
            csv << t_sec << "," << freq << "\n";
            t_sec += 1.0 / SAMPLE_RATE;
        }

        if (step % 10 == 0) {
            std::cout << "[TB] Step " << step << "/" << NUM_STEPS
                      << " (" << (int)freq << " Hz, "
                      << dwell_samples << " samples)" << std::endl;
        }
    }

    if (g_pdm_bit_count > 0) {
        g_pdm_byte <<= (8 - g_pdm_bit_count);
        g_pdm_file.put(static_cast<char>(g_pdm_byte));
    }

    g_pdm_active = false;
    g_pdm_file.close();
    csv.close();

    top->final();

    std::cout << "\n[TB] PDM samples: " << g_pdm_total
              << " (" << (double)g_pdm_total / PDM_RATE_HZ << "s)" << std::endl;
    return 0;
}