//-------------------------------------------------------------------------------------------------
//
//  File: sim_sid_plyaer.cpp
//  Description: Verilator testbench for TT6581.
//               Plays SID stimulus captured from a MOS6502 emulator.
//
//  Author:
//    - Andreas Pedersen
//
//-------------------------------------------------------------------------------------------------

#include <memory>
#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <string>
#include <cstdint>
#include <verilated.h>
#include "Vtb_sid_player.h"

#define CLK_PERIOD_NS 20
#define SPI_CLK_DIV   2

// PDM (Delta-Sigma)
const int    CYCLES_PER_DAC = 5;         // 50 MHz / 10 MHz
const int    PDM_RATE_HZ    = 10000000;  // 10 MHz DAC rate

static std::ofstream g_pdm_file;
static uint8_t  g_pdm_byte      = 0;
static int      g_pdm_bit_count = 0;
static uint64_t g_pdm_total     = 0;
static bool     g_pdm_active    = false;

struct StimulusEvent {
    uint64_t clk_tick;
    uint8_t  addr;
    uint8_t  data;
};

static uint64_t g_clk_count = 0;

void sys_tick(const std::unique_ptr<VerilatedContext>& ctx,
              const std::unique_ptr<Vtb_sid_player>& top) {
    top->clk_i = 0;
    top->eval();
    ctx->timeInc(CLK_PERIOD_NS / 2);

    top->clk_i = 1;
    top->eval();
    ctx->timeInc(CLK_PERIOD_NS / 2);

    // Capture 1-bit PDM output at 10 MHz (every 5th system clock)
    if (g_pdm_active && (g_clk_count % CYCLES_PER_DAC == 0)) {
        g_pdm_byte = (g_pdm_byte << 1) | (top->wave_o & 1);
        g_pdm_bit_count++;
        if (g_pdm_bit_count == 8) {
            g_pdm_file.put(static_cast<char>(g_pdm_byte));
            g_pdm_byte = 0;
            g_pdm_bit_count = 0;
        }
        g_pdm_total++;
    }
    g_clk_count++;
}

// Multi-tick
void tick_batch(const std::unique_ptr<VerilatedContext>& ctx,
                const std::unique_ptr<Vtb_sid_player>& top,
                uint64_t ticks) {
    for (uint64_t i = 0; i < ticks; i++) {
        sys_tick(ctx, top);
    }
}

void spi_write(const std::unique_ptr<VerilatedContext>& ctx,
               const std::unique_ptr<Vtb_sid_player>& top,
               uint8_t addr, uint8_t data) {
    uint16_t frame = (addr << 8) | data;
    frame = 0x8000 | frame;
    top->cs_i = 0;
    for (int i = 15; i >= 0; i--) {
        top->mosi_i = (frame >> i) & 1;
        for(int k=0; k<SPI_CLK_DIV/2; k++) {
            sys_tick(ctx, top);
        }
        top->sclk_i = 1;
        for(int k=0; k<SPI_CLK_DIV/2; k++) {
            sys_tick(ctx, top);
        }
        top->sclk_i = 0;
    }

    for(int k=0; k<SPI_CLK_DIV/2; k++) sys_tick(ctx, top);
    top->cs_i = 1;

    for(int k=0; k<20; k++) sys_tick(ctx, top);
}

std::vector<StimulusEvent> load_stimulus(const std::string& path) {
    std::vector<StimulusEvent> events;
    std::ifstream file(path);

    std::string line;
    while (std::getline(file, line)) {
        if (line.empty() || line[0] == '#') continue;

        StimulusEvent ev;
        unsigned addr, data;
        std::istringstream iss(line);

        iss >> ev.clk_tick;

        std::string token;
        iss >> token;
        addr = std::stoul(token, nullptr, 16);
        ev.addr = addr;

        iss >> token;
        data = std::stoul(token, nullptr, 16);
        ev.data = data;

        events.push_back(ev);
    }

    return events;
}

int main(int argc, char** argv) {
    Verilated::mkdir("logs");
    const std::unique_ptr<VerilatedContext> contextp{new VerilatedContext};
    contextp->commandArgs(argc, argv);
    const std::unique_ptr<Vtb_sid_player> top{new Vtb_sid_player{contextp.get(), "TOP"}};

    std::string stim_path = "stimulus/Hubbard_Rob_Monty_on_the_Run_tt6581_stimulus.txt";
    for (int i = 1; i < argc; i++) {
        std::string arg(argv[i]);
        if (arg.rfind("+stimulus=", 0) == 0) {
            stim_path = arg.substr(10);
        }
    }

    std::cout << "[TB] TT6581 SID Player" << std::endl;
    std::cout << "Loading stimulus: " << stim_path << std::endl;

    auto events = load_stimulus(stim_path);
    std::cout << "Loaded " << events.size() << " register writes" << std::endl;

    g_pdm_file.open("tmp/pdm_out.bin", std::ios::binary);

    // Reset
    top->clk_i  = 0;
    top->rst_ni = 0;
    top->sclk_i = 0;
    top->cs_i   = 1;
    top->mosi_i = 0;

    // Constants
    const int    SAMPLE_RATE       = 50000;
    const int    TICKS_PER_SAMPLE  = 50000000 / SAMPLE_RATE;
    const uint64_t last_event_tick = events.back().clk_tick;
    const uint64_t total_ticks     = last_event_tick + SAMPLE_RATE * TICKS_PER_SAMPLE;

    const float duration_s = (float)total_ticks / 50000000.0f;
    std::cout << "Simulation duration: " << duration_s << "s "
              << "(" << total_ticks << " ticks)" << std::endl;
    std::cout << "PDM output: 10 MHz, 1-bit, packed binary" << std::endl;

    // ── Reset sequence ──────────────────────────────────────────────────────
    for (int i = 0; i < 5; i++) {
        sys_tick(contextp, top);
    }
    top->rst_ni = 1;
    for (int i = 0; i < 5; i++) {
        sys_tick(contextp, top);
    }

    g_pdm_active = true;

    size_t event_idx     = 0;
    uint64_t sample_count = 0;
    uint64_t next_sample  = TICKS_PER_SAMPLE;

    while (g_clk_count < total_ticks) {
        while (event_idx < events.size() && events[event_idx].clk_tick <= g_clk_count) {
            auto& ev = events[event_idx];
            spi_write(contextp, top, ev.addr, ev.data);
            event_idx++;
        }

        uint64_t target = total_ticks;
        if (event_idx < events.size()) {
            target = std::min(target, events[event_idx].clk_tick);
        }
        target = std::min(target, next_sample);

        if (target > g_clk_count) {
            tick_batch(contextp, top, target - g_clk_count);
        } else {
            sys_tick(contextp, top);
        }

        if (g_clk_count >= next_sample) {
            sample_count++;
            next_sample = (sample_count + 1) * TICKS_PER_SAMPLE;

            if (sample_count % SAMPLE_RATE == 0) {
                std::cout << "[TB] Time: " << (sample_count / SAMPLE_RATE)
                          << "s  Events: " << event_idx << "/" << events.size()
                          << std::endl;
            }
        }
    }

    if (g_pdm_bit_count > 0) {
        g_pdm_byte <<= (8 - g_pdm_bit_count);
        g_pdm_file.put(static_cast<char>(g_pdm_byte));
    }
    g_pdm_file.close();

    top->final();

    std::cout << "[TB] PDM samples captured: " << g_pdm_total
              << " (" << (double)g_pdm_total / PDM_RATE_HZ << "s at "
              << PDM_RATE_HZ / 1000000 << " MHz)" << std::endl;
    return 0;
}
