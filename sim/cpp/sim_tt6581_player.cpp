//-------------------------------------------------------------------------------------------------
//
//  File: sim_tt6581_player.cpp
//  Description: Verilator testbench for TT6581.
//               Plays SID stimulus captured from a MOS6502 emulator.
//
//  Author:
//    - Andreas Pedersen
//
//-------------------------------------------------------------------------------------------------

#include "sim_common.h"
#include "Vtb_tt6581_player.h"

#include <sstream>
#include <vector>

const int SPI_CLK_DIV = 2;  // Fast SPI for stimulus playback

struct StimulusEvent {
    uint64_t clk_tick;
    uint8_t  addr;
    uint8_t  data;
};

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
    contextp->traceEverOn(false);
    const std::unique_ptr<Vtb_tt6581_player> top{new Vtb_tt6581_player{contextp.get(), "TOP"}};

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

    // Load stimulus
    std::string stim_path = "stimulus/Hubbard_Rob_Monty_on_the_Run_tt6581_stimulus.txt";
    for (int i = 1; i < argc; i++) {
        std::string arg(argv[i]);
        if (arg.rfind("+stimulus=", 0) == 0) {
            stim_path = arg.substr(10);
        }
    }

    std::cout << "[TB] TT6581 SID Player" << std::endl;
    std::cout << "[TB] Loading stimulus: " << stim_path << std::endl;

    auto events = load_stimulus(stim_path);
    std::cout << "[TB] Loaded " << events.size() << " register writes" << std::endl;

    pdm.open("tmp/pdm_out.bin");

    // Initial pin state
    top->clk_i  = 0;
    top->rst_ni = 0;
    top->sclk_i = 0;
    top->cs_i   = 1;
    top->mosi_i = 0;

    const uint64_t last_event_tick = events.back().clk_tick;
    const uint64_t total_ticks     = last_event_tick + SAMPLE_RATE_HZ * CYCLES_PER_SAMPLE;

    const float duration_s = (float)total_ticks / CLK_FREQ_HZ;
    std::cout << "[TB] Duration: " << duration_s << "s ("
              << total_ticks << " ticks)" << std::endl;
    std::cout << "[TB] PDM output: 10 MHz, 1-bit, packed binary" << std::endl;

    // Reset
    for (int i = 0; i < 5; i++) sys_tick();
    top->rst_ni = 1;
    for (int i = 0; i < 5; i++) sys_tick();

    pdm.active = true;

    size_t   event_idx    = 0;
    uint64_t sample_count = 0;
    uint64_t next_sample  = CYCLES_PER_SAMPLE;

    while (tick_count < total_ticks) {
        while (event_idx < events.size() && events[event_idx].clk_tick <= tick_count) {
            auto& ev = events[event_idx];
            spi_write(top, sys_tick, ev.addr, ev.data, SPI_CLK_DIV);
            event_idx++;
        }

        uint64_t target = total_ticks;
        if (event_idx < events.size()) {
            target = std::min(target, events[event_idx].clk_tick);
        }
        target = std::min(target, next_sample);

        if (target > tick_count) {
            sys_tick_batch(target - tick_count);
        } else {
            sys_tick();
        }

        if (tick_count >= next_sample) {
            sample_count++;
            next_sample = (sample_count + 1) * CYCLES_PER_SAMPLE;

            if (sample_count % SAMPLE_RATE_HZ == 0) {
                std::cout << "[TB] Time: " << (sample_count / SAMPLE_RATE_HZ)
                          << "s  Events: " << event_idx << "/" << events.size()
                          << std::endl;
            }
        }
    }

    pdm.flush();
    top->final();

    std::cout << "[TB] PDM samples captured: " << pdm.total
              << " (" << (double)pdm.total / DAC_RATE_HZ << "s at "
              << DAC_RATE_HZ / 1000000 << " MHz)" << std::endl;
    return 0;
}
