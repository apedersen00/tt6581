//-------------------------------------------------------------------------------------------------
//
//  File: sim_tt6581.cpp
//  Description: Verilator testbench for TT6581.
//               Plays a 10 second song utilizing most of the TT6581.
//
//  Author:
//    - Andreas Pedersen
//
//-------------------------------------------------------------------------------------------------

#include "sim_common.h"
#include "Vtb_tt6581.h"

#include <vector>
#include <algorithm>

// Notes
const double C2  = 65.41,  D2  = 73.42,  Eb2 = 77.78,  F2  = 87.31;
const double G2  = 98.00,  Ab2 = 103.83, Bb2 = 116.54, B2  = 123.47;
const double C3  = 130.81, D3  = 146.83, Eb3 = 155.56, F3  = 174.61;
const double G3  = 196.00, Ab3 = 207.65, Bb3 = 233.08, B3  = 246.94;
const double C4  = 261.63, D4  = 293.66, Eb4 = 311.13, F4  = 349.23;
const double G4  = 392.00, Ab4 = 415.30, Bb4 = 466.16, B4  = 493.88;
const double C5  = 523.25, D5  = 587.33, Eb5 = 622.25, G5  = 783.99;

enum class EventType { GATE_ON, GATE_OFF, FREQ_ONLY };

struct NoteEvent {
    uint64_t  sample;
    uint8_t   voice;
    double    freq;
    uint8_t   wave;
    EventType type;
};

struct FilterEvent {
    uint64_t sample;
    double   fc;
    double   q;
    uint8_t  en_mode;
};

void add_filter_event(std::vector<FilterEvent>& events, double time_s,
                      double fc, double q, uint8_t en_mode, int sr) {
    uint64_t s = (uint64_t)(time_s * sr);
    events.push_back({s, fc, q, en_mode});
}

// Add a note with automatic gate-off before the end (for envelope retrigger)
void add_note(std::vector<NoteEvent>& events, double time_s,
              uint8_t voice, double freq, double dur_s, uint8_t wave,
              int sr, double release_gap = 0.03) {
    uint64_t on  = (uint64_t)(time_s * sr);
    uint64_t off = (uint64_t)((time_s + dur_s - release_gap) * sr);
    events.push_back({on,  voice, freq, wave, EventType::GATE_ON});
    events.push_back({off, voice, 0,    wave, EventType::GATE_OFF});
}

// Add arpeggio cycling through 3 notes (gate stays on, only freq changes)
void add_arpeggio(std::vector<NoteEvent>& events,
                  double start_s, double end_s,
                  uint8_t voice, uint8_t wave,
                  double f1, double f2, double f3, int sr) {
    const double step = 0.125;
    double freqs[] = {f1, f2, f3};
    // Initial gate on
    events.push_back({(uint64_t)(start_s * sr), voice, f1, wave, EventType::GATE_ON});
    double t = start_s + step;
    int idx = 1;
    while (t < end_s - 0.05) {
        events.push_back({(uint64_t)(t * sr), voice, freqs[idx % 3], wave, EventType::FREQ_ONLY});
        t += step;
        idx++;
    }
    // Gate off at end
    events.push_back({(uint64_t)((end_s - 0.02) * sr), voice, 0, wave, EventType::GATE_OFF});
}

int main(int argc, char** argv) {
    Verilated::mkdir("logs");
    const std::unique_ptr<VerilatedContext> contextp{new VerilatedContext};
    contextp->commandArgs(argc, argv);
    contextp->traceEverOn(false);
    const std::unique_ptr<Vtb_tt6581> top{new Vtb_tt6581{contextp.get(), "TOP"}};

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

    pdm.open("tmp/pdm_out.bin");

    // Initial pin state
    top->clk_i  = 0;
    top->rst_ni = 0;
    top->sclk_i = 0;
    top->cs_i   = 1;
    top->mosi_i = 0;

    const float  DURATION = 10.0;
    const double Q = 0.5;   // quarter note at 120 BPM
    const double E = 0.25;  // eighth note
    const double H = 1.0;   // half note

    uint64_t max_samples   = DURATION * SAMPLE_RATE_HZ;
    uint64_t total_samples = 0;

    std::cout << "[TB] TT6581 Test Song" << std::endl;
    std::cout << "[TB] Duration: " << DURATION << "s (" << max_samples << " samples)" << std::endl;
    std::cout << "[TB] PDM output: 10 MHz, 1-bit, packed binary" << std::endl;

    // Reset
    for (int i = 0; i < 5; i++) sys_tick();
    top->rst_ni = 1;
    for (int i = 0; i < 5; i++) sys_tick();

    // Voice 1: Lead (Pulse 25% duty cycle)
    spi_write(top, sys_tick, V1_BASE + REG_PW_LO, 0x00);
    spi_write(top, sys_tick, V1_BASE + REG_PW_HI, 0x04);  // PW = 0x400 = 25%
    set_adsr(top, sys_tick, V1_BASE, 2, 6, 10, 5);

    // Voice 2: Bass (Sawtooth)
    set_adsr(top, sys_tick, V2_BASE, 0, 5, 10, 3);

    // Voice 3: Arpeggio (Triangle)
    set_adsr(top, sys_tick, V3_BASE, 0, 2, 15, 3);

    // Volume
    spi_write(top, sys_tick, FILT_BASE + REG_VOLUME, 0xFF);

    // Initial filter: warm low-pass, all voices routed, Butterworth Q
    const uint8_t FILT_ALL_LP = FILT_V1 | FILT_V2 | FILT_V3 | FILT_LP;
    const uint8_t FILT_ALL_HP = FILT_V1 | FILT_V2 | FILT_V3 | FILT_HP;
    set_filter(top, sys_tick, 600.0, 0.707, FILT_ALL_LP);

    std::vector<NoteEvent> song;

    // Voice 1
    add_note(song, 1.00, V1_BASE, G4,  E, WAVE_PULSE, SAMPLE_RATE_HZ);
    add_note(song, 1.25, V1_BASE, Eb4, E, WAVE_PULSE, SAMPLE_RATE_HZ);
    add_note(song, 1.50, V1_BASE, C4,  Q, WAVE_PULSE, SAMPLE_RATE_HZ);

    add_note(song, 2.00, V1_BASE, F4,  E, WAVE_PULSE, SAMPLE_RATE_HZ);
    add_note(song, 2.25, V1_BASE, Ab4, E, WAVE_PULSE, SAMPLE_RATE_HZ);
    add_note(song, 2.50, V1_BASE, G4,  Q, WAVE_PULSE, SAMPLE_RATE_HZ);
    add_note(song, 3.00, V1_BASE, Eb4, E, WAVE_PULSE, SAMPLE_RATE_HZ);
    add_note(song, 3.25, V1_BASE, D4,  E, WAVE_PULSE, SAMPLE_RATE_HZ);
    add_note(song, 3.50, V1_BASE, C4,  Q, WAVE_PULSE, SAMPLE_RATE_HZ);

    add_note(song, 4.00, V1_BASE, Eb4, E, WAVE_PULSE, SAMPLE_RATE_HZ);
    add_note(song, 4.25, V1_BASE, G4,  E, WAVE_PULSE, SAMPLE_RATE_HZ);
    add_note(song, 4.50, V1_BASE, Ab4, Q, WAVE_PULSE, SAMPLE_RATE_HZ);
    add_note(song, 5.00, V1_BASE, Bb4, E, WAVE_PULSE, SAMPLE_RATE_HZ);
    add_note(song, 5.25, V1_BASE, Ab4, E, WAVE_PULSE, SAMPLE_RATE_HZ);
    add_note(song, 5.50, V1_BASE, G4,  Q, WAVE_PULSE, SAMPLE_RATE_HZ);

    add_note(song, 6.00, V1_BASE, F4,  E, WAVE_PULSE, SAMPLE_RATE_HZ);
    add_note(song, 6.25, V1_BASE, Ab4, E, WAVE_PULSE, SAMPLE_RATE_HZ);
    add_note(song, 6.50, V1_BASE, G4,  Q, WAVE_PULSE, SAMPLE_RATE_HZ);
    add_note(song, 7.00, V1_BASE, F4,  E, WAVE_PULSE, SAMPLE_RATE_HZ);
    add_note(song, 7.25, V1_BASE, Eb4, E, WAVE_PULSE, SAMPLE_RATE_HZ);
    add_note(song, 7.50, V1_BASE, D4,  Q, WAVE_PULSE, SAMPLE_RATE_HZ);

    add_note(song, 8.00, V1_BASE, C5,  H, WAVE_PULSE, SAMPLE_RATE_HZ);
    add_note(song, 9.00, V1_BASE, G4,  Q, WAVE_PULSE, SAMPLE_RATE_HZ);
    add_note(song, 9.50, V1_BASE, C4,  Q, WAVE_PULSE, SAMPLE_RATE_HZ, 0.15);

    // Voice 2
    add_note(song, 0.00, V2_BASE, C2,  Q, WAVE_SAW, SAMPLE_RATE_HZ);
    add_note(song, 0.50, V2_BASE, G2,  Q, WAVE_SAW, SAMPLE_RATE_HZ);
    add_note(song, 1.00, V2_BASE, C2,  Q, WAVE_SAW, SAMPLE_RATE_HZ);
    add_note(song, 1.50, V2_BASE, G2,  Q, WAVE_SAW, SAMPLE_RATE_HZ);

    add_note(song, 2.00, V2_BASE, F2,  Q, WAVE_SAW, SAMPLE_RATE_HZ);
    add_note(song, 2.50, V2_BASE, C3,  Q, WAVE_SAW, SAMPLE_RATE_HZ);
    add_note(song, 3.00, V2_BASE, G2,  Q, WAVE_SAW, SAMPLE_RATE_HZ);
    add_note(song, 3.50, V2_BASE, D3,  Q, WAVE_SAW, SAMPLE_RATE_HZ);

    add_note(song, 4.00, V2_BASE, Ab2, Q, WAVE_SAW, SAMPLE_RATE_HZ);
    add_note(song, 4.50, V2_BASE, Eb3, Q, WAVE_SAW, SAMPLE_RATE_HZ);
    add_note(song, 5.00, V2_BASE, Bb2, Q, WAVE_SAW, SAMPLE_RATE_HZ);
    add_note(song, 5.50, V2_BASE, F3,  Q, WAVE_SAW, SAMPLE_RATE_HZ);

    add_note(song, 6.00, V2_BASE, F2,  Q, WAVE_SAW, SAMPLE_RATE_HZ);
    add_note(song, 6.50, V2_BASE, C3,  Q, WAVE_SAW, SAMPLE_RATE_HZ);
    add_note(song, 7.00, V2_BASE, G2,  Q, WAVE_SAW, SAMPLE_RATE_HZ);
    add_note(song, 7.50, V2_BASE, D3,  Q, WAVE_SAW, SAMPLE_RATE_HZ);

    add_note(song, 8.00, V2_BASE, C2,  Q, WAVE_SAW, SAMPLE_RATE_HZ);
    add_note(song, 8.50, V2_BASE, G2,  Q, WAVE_SAW, SAMPLE_RATE_HZ);
    add_note(song, 9.00, V2_BASE, C3,  Q, WAVE_SAW, SAMPLE_RATE_HZ, 0.15);

    // Voice 3
    add_arpeggio(song, 0.0, 2.0, V3_BASE, WAVE_TRI, C4, Eb4, G4, SAMPLE_RATE_HZ);

    add_arpeggio(song, 2.0, 3.0, V3_BASE, WAVE_TRI, F3, Ab3, C4, SAMPLE_RATE_HZ);
    add_arpeggio(song, 3.0, 4.0, V3_BASE, WAVE_TRI, G3, B3,  D4, SAMPLE_RATE_HZ);

    add_arpeggio(song, 4.0, 5.0, V3_BASE, WAVE_TRI, Ab3, C4, Eb4, SAMPLE_RATE_HZ);
    add_arpeggio(song, 5.0, 6.0, V3_BASE, WAVE_TRI, Bb3, D4, F4,  SAMPLE_RATE_HZ);

    add_arpeggio(song, 6.0, 7.0, V3_BASE, WAVE_TRI, F3, Ab3, C4, SAMPLE_RATE_HZ);
    add_arpeggio(song, 7.0, 8.0, V3_BASE, WAVE_TRI, G3, B3,  D4, SAMPLE_RATE_HZ);

    add_arpeggio(song, 8.0, 9.5, V3_BASE, WAVE_TRI, C4, Eb4, G4, SAMPLE_RATE_HZ);

    // Filter events
    std::vector<FilterEvent> filter_song;

    // Low pass sweep in the beginning
    add_filter_event(filter_song, 0.00, 600.0,  1.0,   FILT_ALL_LP, SAMPLE_RATE_HZ);
    add_filter_event(filter_song, 0.50, 800.0,  1.0,   FILT_ALL_LP, SAMPLE_RATE_HZ);
    add_filter_event(filter_song, 1.00, 1200.0, 0.9,   FILT_ALL_LP, SAMPLE_RATE_HZ);
    add_filter_event(filter_song, 1.50, 1500.0, 0.8,   FILT_ALL_LP, SAMPLE_RATE_HZ);

    add_filter_event(filter_song, 2.00, 2000.0, 1.0,   FILT_ALL_LP, SAMPLE_RATE_HZ);
    add_filter_event(filter_song, 2.50, 2200.0, 1.2,   FILT_ALL_LP, SAMPLE_RATE_HZ);
    add_filter_event(filter_song, 3.00, 2500.0, 1.5,   FILT_ALL_LP, SAMPLE_RATE_HZ);
    add_filter_event(filter_song, 3.50, 2800.0, 1.2,   FILT_ALL_LP, SAMPLE_RATE_HZ);

    add_filter_event(filter_song, 4.00, 3500.0, 2.0,   FILT_ALL_LP, SAMPLE_RATE_HZ);
    add_filter_event(filter_song, 4.50, 4000.0, 2.5,   FILT_ALL_LP, SAMPLE_RATE_HZ);
    add_filter_event(filter_song, 5.00, 5000.0, 2.0,   FILT_ALL_LP, SAMPLE_RATE_HZ);
    add_filter_event(filter_song, 6.00, 8000.0, 1.2,   FILT_ALL_LP, SAMPLE_RATE_HZ);

    // High pass end
    add_filter_event(filter_song, 9.00, 100.0,   0.707, FILT_ALL_HP, SAMPLE_RATE_HZ);
    add_filter_event(filter_song, 9.50, 4000.0, 1.5,   FILT_ALL_HP, SAMPLE_RATE_HZ);

    std::sort(filter_song.begin(), filter_song.end(),
        [](const FilterEvent& a, const FilterEvent& b) { return a.sample < b.sample; });

    std::sort(song.begin(), song.end(),
        [](const NoteEvent& a, const NoteEvent& b) { return a.sample < b.sample; });

    tick_count = 0;
    pdm.active = true;

    size_t event_idx = 0;
    size_t filt_idx  = 0;

    while (total_samples < max_samples) {
        while (event_idx < song.size() && song[event_idx].sample <= total_samples) {
            auto& ev = song[event_idx];
            switch (ev.type) {
                case EventType::GATE_ON:
                    set_voice_freq(top, sys_tick, ev.voice, ev.freq);
                    set_control(top, sys_tick, ev.voice, ev.wave, true);
                    break;
                case EventType::GATE_OFF:
                    set_control(top, sys_tick, ev.voice, ev.wave, false);
                    break;
                case EventType::FREQ_ONLY:
                    set_voice_freq(top, sys_tick, ev.voice, ev.freq);
                    break;
            }
            event_idx++;
        }

        while (filt_idx < filter_song.size() && filter_song[filt_idx].sample <= total_samples) {
            auto& fe = filter_song[filt_idx];
            set_filter(top, sys_tick, fe.fc, fe.q, fe.en_mode);
            filt_idx++;
        }

        sys_tick_batch(CYCLES_PER_SAMPLE);
        total_samples++;

        if (total_samples % SAMPLE_RATE_HZ == 0) {
            std::cout << "[TB] Time: " << (total_samples / SAMPLE_RATE_HZ)
                      << "s / " << (int)DURATION << "s" << std::endl;
        }
    }

    pdm.flush();
    top->final();

    std::cout << "[TB] PDM samples captured: " << pdm.total
              << " (" << (double)pdm.total / DAC_RATE_HZ << "s at "
              << DAC_RATE_HZ / 1000000 << " MHz)" << std::endl;
    return 0;
}
