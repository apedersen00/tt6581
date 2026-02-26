//-------------------------------------------------------------------------------------------------
// File: sim_tt6581.cpp
// Description: Top-level testbench for TT6581 with SPI Master simulation and Audio Dump
//-------------------------------------------------------------------------------------------------

#include <memory>
#include <iostream>
#include <fstream>
#include <vector>
#include <algorithm>
#include <cmath>
#include <verilated.h>
#include "Vtb_tt6581.h"

#define CLK_PERIOD_NS 20   // 50 MHz System Clock
#define SPI_CLK_DIV   20   // SPI is 20x slower than SysClk (2.5 MHz)

// PDM (Delta-Sigma) capture constants
const int    CYCLES_PER_DAC = 5;         // 50 MHz / 10 MHz
const int    PDM_RATE_HZ    = 10000000;  // 10 MHz DAC rate

// Global PDM capture state
static std::ofstream g_pdm_file;
static uint8_t  g_pdm_byte      = 0;
static int      g_pdm_bit_count = 0;
static uint64_t g_pdm_total     = 0;
static uint64_t g_tick_count    = 0;
static bool     g_pdm_active    = false;

const uint8_t V1_BASE = 0x00;
const uint8_t V2_BASE = 0x07;
const uint8_t V3_BASE = 0x0E;

const uint8_t REG_FREQ_LO = 0x00;
const uint8_t REG_FREQ_HI = 0x01;
const uint8_t REG_PW_LO   = 0x02;
const uint8_t REG_PW_HI   = 0x03;
const uint8_t REG_CTRL    = 0x04;
const uint8_t REG_AD      = 0x05;
const uint8_t REG_SR      = 0x06;

// ─── Filter Registers (base 0x15) ───────────────────────────────────────────────
const uint8_t FILT_BASE    = 0x15;
const uint8_t REG_F_LO     = 0x00;
const uint8_t REG_F_HI     = 0x01;
const uint8_t REG_Q_LO     = 0x02;
const uint8_t REG_Q_HI     = 0x03;
const uint8_t REG_EN_MODE  = 0x04;
const uint8_t REG_VOLUME   = 0x05;

// Filter mode bits (EN_MODE[2:0])
const uint8_t FILT_LP = 0x01;  // Low-pass
const uint8_t FILT_BP = 0x02;  // Band-pass
const uint8_t FILT_HP = 0x04;  // High-pass

// Voice filter enable bits (EN_MODE[5:3])
const uint8_t FILT_V1 = 0x08;  // bit 3
const uint8_t FILT_V2 = 0x10;  // bit 4
const uint8_t FILT_V3 = 0x20;  // bit 5;

void sys_tick(const std::unique_ptr<VerilatedContext>& ctx,
              const std::unique_ptr<Vtb_tt6581>& top) {
    top->clk_i = 0;
    top->eval();
    ctx->timeInc(CLK_PERIOD_NS / 2);

    top->clk_i = 1;
    top->eval();
    ctx->timeInc(CLK_PERIOD_NS / 2);

    // Capture 1-bit PDM output at 10 MHz (every 5th system clock)
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
                const std::unique_ptr<Vtb_tt6581>& top,
                int ticks) {
    for(int i = 0; i < ticks; i++) {
        sys_tick(ctx, top);
    }
}

void spi_write(const std::unique_ptr<VerilatedContext>& ctx,
               const std::unique_ptr<Vtb_tt6581>& top,
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

uint16_t calc_fcw(double freq) {
    uint64_t numerator = (uint64_t)freq * (1ULL << 19);
    return (uint16_t)(numerator / 50000ULL);
}

void set_voice_freq(const std::unique_ptr<VerilatedContext>& ctx,
                    const std::unique_ptr<Vtb_tt6581>& top,
                    uint8_t base_addr, double freq) {
    uint16_t fcw = calc_fcw(freq);
    spi_write(ctx, top, base_addr + REG_FREQ_LO, fcw & 0xFF);
    spi_write(ctx, top, base_addr + REG_FREQ_HI, (fcw >> 8) & 0xFF);
}

void setup_voice(const std::unique_ptr<VerilatedContext>& ctx,
                 const std::unique_ptr<Vtb_tt6581>& top,
                 uint8_t base_addr, uint8_t wave_ctrl) {
    // Set Pulse Width to 50% (0x0800)
    spi_write(ctx, top, base_addr + REG_PW_LO, 0x00);
    spi_write(ctx, top, base_addr + REG_PW_HI, 0x08);
    // Set Waveform Control
    spi_write(ctx, top, base_addr + REG_CTRL, wave_ctrl);
}

void set_adsr(const std::unique_ptr<VerilatedContext>& ctx,
              const std::unique_ptr<Vtb_tt6581>& top,
              uint8_t base_addr, 
              uint8_t attack, uint8_t decay, 
              uint8_t sustain, uint8_t release) {
    
    uint8_t ad = ((attack & 0x0F) << 4) | (decay & 0x0F);
    uint8_t sr = ((sustain & 0x0F) << 4) | (release & 0x0F);

    spi_write(ctx, top, base_addr + REG_AD, ad);
    spi_write(ctx, top, base_addr + REG_SR, sr);
}

void set_control(const std::unique_ptr<VerilatedContext>& ctx,
                 const std::unique_ptr<Vtb_tt6581>& top,
                 uint8_t base_addr, 
                 uint8_t waveform_mask, bool gate) {
    
    uint8_t ctrl = waveform_mask;
    if (gate) ctrl |= 0x01; // Set Gate Bit (Bit 0)
    
    spi_write(ctx, top, base_addr + REG_CTRL, ctrl);
}

int16_t get_coeff_f(double fc) {
    double f = 2.0 * std::sin(M_PI * fc / 50000.0);
    return (int16_t)(f * 32768.0);
}

int16_t get_coeff_q(double q) {
    double q_damp = 1.0 / q;
    return (int16_t)(q_damp * 4096.0);
}

void set_filter(const std::unique_ptr<VerilatedContext>& ctx,
               const std::unique_ptr<Vtb_tt6581>& top,
               double fc, double q, uint8_t en_mode) {
    int16_t cf = get_coeff_f(fc);
    int16_t cq = get_coeff_q(q);
    spi_write(ctx, top, FILT_BASE + REG_F_LO, cf & 0xFF);
    spi_write(ctx, top, FILT_BASE + REG_F_HI, (cf >> 8) & 0xFF);
    spi_write(ctx, top, FILT_BASE + REG_Q_LO, cq & 0xFF);
    spi_write(ctx, top, FILT_BASE + REG_Q_HI, (cq >> 8) & 0xFF);
    spi_write(ctx, top, FILT_BASE + REG_EN_MODE, en_mode);
}

// ─── Waveform Select Masks ──────────────────────────────────────────────────────
const uint8_t WAVE_TRI   = 0x10;
const uint8_t WAVE_SAW   = 0x20;
const uint8_t WAVE_PULSE = 0x40;

// ─── Note Frequencies (Hz) ──────────────────────────────────────────────────────
const double C2  = 65.41,  D2  = 73.42,  Eb2 = 77.78,  F2  = 87.31;
const double G2  = 98.00,  Ab2 = 103.83, Bb2 = 116.54, B2  = 123.47;
const double C3  = 130.81, D3  = 146.83, Eb3 = 155.56, F3  = 174.61;
const double G3  = 196.00, Ab3 = 207.65, Bb3 = 233.08, B3  = 246.94;
const double C4  = 261.63, D4  = 293.66, Eb4 = 311.13, F4  = 349.23;
const double G4  = 392.00, Ab4 = 415.30, Bb4 = 466.16, B4  = 493.88;
const double C5  = 523.25, D5  = 587.33, Eb5 = 622.25, G5  = 783.99;

// ─── Song Event System ──────────────────────────────────────────────────────────
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
    double   fc;       // Cutoff frequency (Hz)
    double   q;        // Resonance (Q factor)
    uint8_t  en_mode;  // Voice enable | filter mode
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
    const double step = 0.125; // sixteenth note at 120 BPM
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

// ─── Main ───────────────────────────────────────────────────────────────────────
int main(int argc, char** argv) {
    Verilated::mkdir("logs");
    const std::unique_ptr<VerilatedContext> contextp{new VerilatedContext};
    contextp->commandArgs(argc, argv);
    contextp->traceEverOn(true);
    const std::unique_ptr<Vtb_tt6581> top{new Vtb_tt6581{contextp.get(), "TOP"}};

    g_pdm_file.open("pdm_output.bin", std::ios::binary);
    if (!g_pdm_file.is_open()) {
        std::cerr << "Error: Could not open pdm_output.bin" << std::endl;
        return 1;
    }

    // Initial pin state
    top->clk_i  = 0;
    top->rst_ni = 0;
    top->sclk_i = 0;
    top->cs_i   = 1;
    top->mosi_i = 0;

    const float  DURATION         = 10.0;
    const int    SAMPLE_RATE      = 50000;
    const int    TICKS_PER_SAMPLE = 50000000 / SAMPLE_RATE;
    const double Q = 0.5;   // quarter note at 120 BPM
    const double E = 0.25;  // eighth note
    const double H = 1.0;   // half note

    uint64_t max_samples   = DURATION * SAMPLE_RATE;
    uint64_t total_samples = 0;

    // ── Reset sequence ──────────────────────────────────────────────────────────
    for (int i = 0; i < 50; i++) sys_tick(contextp, top);
    top->rst_ni = 1;
    for (int i = 0; i < 50; i++) sys_tick(contextp, top);

    // ── Voice Setup ─────────────────────────────────────────────────────────────
    // Voice 1: Lead (Pulse 25% duty cycle)
    spi_write(contextp, top, V1_BASE + REG_PW_LO, 0x00);
    spi_write(contextp, top, V1_BASE + REG_PW_HI, 0x04);  // PW = 0x400 = 25%
    set_adsr(contextp, top, V1_BASE, 2, 6, 10, 5);

    // Voice 2: Bass (Sawtooth)
    set_adsr(contextp, top, V2_BASE, 0, 5, 10, 3);

    // Voice 3: Arpeggio (Triangle)
    set_adsr(contextp, top, V3_BASE, 0, 2, 15, 3);

    // Volume
    spi_write(contextp, top, FILT_BASE + REG_VOLUME, 0x50);

    // Initial filter: warm low-pass, all voices routed, Butterworth Q
    const uint8_t FILT_ALL_LP = FILT_V1 | FILT_V2 | FILT_V3 | FILT_LP;
    set_filter(contextp, top, 600.0, 1.0, FILT_ALL_LP);

    // ── Compose Song: "Nocturne in C Minor" ─────────────────────────────────────
    //
    //   Key: C minor    Tempo: 120 BPM    Time: 4/4
    //   Progression: | Cm | Fm  G | Ab  Bb | Fm  G | Cm |
    //
    //   V1 = Lead melody (Pulse)   V2 = Bass (Saw)   V3 = Arp (Triangle)
    //
    std::vector<NoteEvent> song;

    // ── Voice 1: Lead Melody (Pulse wave) ───────────────────────────────────────
    // Bar 1 (0.0-2.0s) Cm: rest then descending C minor motif
    add_note(song, 1.00, V1_BASE, G4,  E, WAVE_PULSE, SAMPLE_RATE);
    add_note(song, 1.25, V1_BASE, Eb4, E, WAVE_PULSE, SAMPLE_RATE);
    add_note(song, 1.50, V1_BASE, C4,  Q, WAVE_PULSE, SAMPLE_RATE);

    // Bar 2 (2.0-4.0s) Fm → G: ascending then descending
    add_note(song, 2.00, V1_BASE, F4,  E, WAVE_PULSE, SAMPLE_RATE);
    add_note(song, 2.25, V1_BASE, Ab4, E, WAVE_PULSE, SAMPLE_RATE);
    add_note(song, 2.50, V1_BASE, G4,  Q, WAVE_PULSE, SAMPLE_RATE);
    add_note(song, 3.00, V1_BASE, Eb4, E, WAVE_PULSE, SAMPLE_RATE);
    add_note(song, 3.25, V1_BASE, D4,  E, WAVE_PULSE, SAMPLE_RATE);
    add_note(song, 3.50, V1_BASE, C4,  Q, WAVE_PULSE, SAMPLE_RATE);

    // Bar 3 (4.0-6.0s) Ab → Bb: reaching higher
    add_note(song, 4.00, V1_BASE, Eb4, E, WAVE_PULSE, SAMPLE_RATE);
    add_note(song, 4.25, V1_BASE, G4,  E, WAVE_PULSE, SAMPLE_RATE);
    add_note(song, 4.50, V1_BASE, Ab4, Q, WAVE_PULSE, SAMPLE_RATE);
    add_note(song, 5.00, V1_BASE, Bb4, E, WAVE_PULSE, SAMPLE_RATE);
    add_note(song, 5.25, V1_BASE, Ab4, E, WAVE_PULSE, SAMPLE_RATE);
    add_note(song, 5.50, V1_BASE, G4,  Q, WAVE_PULSE, SAMPLE_RATE);

    // Bar 4 (6.0-8.0s) Fm → G: tension and approach
    add_note(song, 6.00, V1_BASE, F4,  E, WAVE_PULSE, SAMPLE_RATE);
    add_note(song, 6.25, V1_BASE, Ab4, E, WAVE_PULSE, SAMPLE_RATE);
    add_note(song, 6.50, V1_BASE, G4,  Q, WAVE_PULSE, SAMPLE_RATE);
    add_note(song, 7.00, V1_BASE, F4,  E, WAVE_PULSE, SAMPLE_RATE);
    add_note(song, 7.25, V1_BASE, Eb4, E, WAVE_PULSE, SAMPLE_RATE);
    add_note(song, 7.50, V1_BASE, D4,  Q, WAVE_PULSE, SAMPLE_RATE);

    // Bar 5 (8.0-10.0s) Cm: resolution
    add_note(song, 8.00, V1_BASE, C5,  H, WAVE_PULSE, SAMPLE_RATE);
    add_note(song, 9.00, V1_BASE, G4,  Q, WAVE_PULSE, SAMPLE_RATE);
    add_note(song, 9.50, V1_BASE, C4,  Q, WAVE_PULSE, SAMPLE_RATE, 0.15);

    // ── Voice 2: Bass Line (Saw wave) ───────────────────────────────────────────
    // Bar 1 (0.0-2.0s) Cm: root-fifth pump
    add_note(song, 0.00, V2_BASE, C2,  Q, WAVE_SAW, SAMPLE_RATE);
    add_note(song, 0.50, V2_BASE, G2,  Q, WAVE_SAW, SAMPLE_RATE);
    add_note(song, 1.00, V2_BASE, C2,  Q, WAVE_SAW, SAMPLE_RATE);
    add_note(song, 1.50, V2_BASE, G2,  Q, WAVE_SAW, SAMPLE_RATE);

    // Bar 2 (2.0-4.0s) Fm → G
    add_note(song, 2.00, V2_BASE, F2,  Q, WAVE_SAW, SAMPLE_RATE);
    add_note(song, 2.50, V2_BASE, C3,  Q, WAVE_SAW, SAMPLE_RATE);
    add_note(song, 3.00, V2_BASE, G2,  Q, WAVE_SAW, SAMPLE_RATE);
    add_note(song, 3.50, V2_BASE, D3,  Q, WAVE_SAW, SAMPLE_RATE);

    // Bar 3 (4.0-6.0s) Ab → Bb
    add_note(song, 4.00, V2_BASE, Ab2, Q, WAVE_SAW, SAMPLE_RATE);
    add_note(song, 4.50, V2_BASE, Eb3, Q, WAVE_SAW, SAMPLE_RATE);
    add_note(song, 5.00, V2_BASE, Bb2, Q, WAVE_SAW, SAMPLE_RATE);
    add_note(song, 5.50, V2_BASE, F3,  Q, WAVE_SAW, SAMPLE_RATE);

    // Bar 4 (6.0-8.0s) Fm → G
    add_note(song, 6.00, V2_BASE, F2,  Q, WAVE_SAW, SAMPLE_RATE);
    add_note(song, 6.50, V2_BASE, C3,  Q, WAVE_SAW, SAMPLE_RATE);
    add_note(song, 7.00, V2_BASE, G2,  Q, WAVE_SAW, SAMPLE_RATE);
    add_note(song, 7.50, V2_BASE, D3,  Q, WAVE_SAW, SAMPLE_RATE);

    // Bar 5 (8.0-10.0s) Cm: sustained resolution
    add_note(song, 8.00, V2_BASE, C2,  Q, WAVE_SAW, SAMPLE_RATE);
    add_note(song, 8.50, V2_BASE, G2,  Q, WAVE_SAW, SAMPLE_RATE);
    add_note(song, 9.00, V2_BASE, C3,  Q, WAVE_SAW, SAMPLE_RATE, 0.15);

    // ── Voice 3: Arpeggiated Chords (Triangle wave) ─────────────────────────────
    // Bar 1 (0.0-2.0s) Cm arpeggio
    add_arpeggio(song, 0.0, 2.0, V3_BASE, WAVE_TRI, C4, Eb4, G4, SAMPLE_RATE);

    // Bar 2 (2.0-4.0s) Fm → G
    add_arpeggio(song, 2.0, 3.0, V3_BASE, WAVE_TRI, F3, Ab3, C4, SAMPLE_RATE);
    add_arpeggio(song, 3.0, 4.0, V3_BASE, WAVE_TRI, G3, B3,  D4, SAMPLE_RATE);

    // Bar 3 (4.0-6.0s) Ab → Bb
    add_arpeggio(song, 4.0, 5.0, V3_BASE, WAVE_TRI, Ab3, C4, Eb4, SAMPLE_RATE);
    add_arpeggio(song, 5.0, 6.0, V3_BASE, WAVE_TRI, Bb3, D4, F4,  SAMPLE_RATE);

    // Bar 4 (6.0-8.0s) Fm → G
    add_arpeggio(song, 6.0, 7.0, V3_BASE, WAVE_TRI, F3, Ab3, C4, SAMPLE_RATE);
    add_arpeggio(song, 7.0, 8.0, V3_BASE, WAVE_TRI, G3, B3,  D4, SAMPLE_RATE);

    // Bar 5 (8.0-10.0s) Cm resolution
    add_arpeggio(song, 8.0, 9.5, V3_BASE, WAVE_TRI, C4, Eb4, G4, SAMPLE_RATE);

    // ── Filter Automation: Dynamic Sweeps ───────────────────────────────────────
    //
    //   Sweep the LP cutoff to follow the harmonic arc of the piece:
    //     dark intro → bright climax → warm resolution
    //
    std::vector<FilterEvent> filter_song;

    // Bar 1 (0-2s) Cm: dark, warm opening
    add_filter_event(filter_song, 0.00, 600.0,  1.0,   FILT_ALL_LP, SAMPLE_RATE);
    add_filter_event(filter_song, 0.50, 800.0,  1.0,   FILT_ALL_LP, SAMPLE_RATE);
    add_filter_event(filter_song, 1.00, 1200.0, 0.9,   FILT_ALL_LP, SAMPLE_RATE);
    add_filter_event(filter_song, 1.50, 1500.0, 0.8,   FILT_ALL_LP, SAMPLE_RATE);

    // Bar 2 (2-4s) Fm → G: opening up
    add_filter_event(filter_song, 2.00, 2000.0, 1.0,   FILT_ALL_LP, SAMPLE_RATE);
    add_filter_event(filter_song, 2.50, 2200.0, 1.2,   FILT_ALL_LP, SAMPLE_RATE);
    add_filter_event(filter_song, 3.00, 2500.0, 1.5,   FILT_ALL_LP, SAMPLE_RATE);
    add_filter_event(filter_song, 3.50, 2800.0, 1.2,   FILT_ALL_LP, SAMPLE_RATE);

    // Bar 3 (4-6s) Ab → Bb: climax — brightest, resonant
    add_filter_event(filter_song, 4.00, 3500.0, 2.0,   FILT_ALL_LP, SAMPLE_RATE);
    add_filter_event(filter_song, 4.50, 4000.0, 2.5,   FILT_ALL_LP, SAMPLE_RATE);
    add_filter_event(filter_song, 5.00, 5000.0, 2.0,   FILT_ALL_LP, SAMPLE_RATE);
    add_filter_event(filter_song, 5.50, 4500.0, 1.5,   FILT_ALL_LP, SAMPLE_RATE);

    // Bar 4 (6-8s) Fm → G: tension receding
    add_filter_event(filter_song, 6.00, 3000.0, 1.2,   FILT_ALL_LP, SAMPLE_RATE);
    add_filter_event(filter_song, 6.50, 2500.0, 1.0,   FILT_ALL_LP, SAMPLE_RATE);
    add_filter_event(filter_song, 7.00, 2000.0, 0.9,   FILT_ALL_LP, SAMPLE_RATE);
    add_filter_event(filter_song, 7.50, 1500.0, 0.8,   FILT_ALL_LP, SAMPLE_RATE);

    // Bar 5 (8-10s) Cm: warm resolution, closing down
    add_filter_event(filter_song, 8.00, 1200.0, 0.707, FILT_ALL_LP, SAMPLE_RATE);
    add_filter_event(filter_song, 8.50, 1000.0, 0.707, FILT_ALL_LP, SAMPLE_RATE);
    add_filter_event(filter_song, 9.00, 700.0,  0.707, FILT_ALL_LP, SAMPLE_RATE);
    add_filter_event(filter_song, 9.50, 400.0,  0.707, FILT_ALL_LP, SAMPLE_RATE);

    // Sort filter events by sample time
    std::sort(filter_song.begin(), filter_song.end(),
        [](const FilterEvent& a, const FilterEvent& b) { return a.sample < b.sample; });

    // ── Sort events by sample time ──────────────────────────────────────────────
    std::sort(song.begin(), song.end(),
        [](const NoteEvent& a, const NoteEvent& b) { return a.sample < b.sample; });

    std::cout << "=== Nocturne in C Minor ==="    << std::endl;
    std::cout << "Key: Cm  Tempo: 120 BPM"       << std::endl;
    std::cout << "V1: Pulse lead  V2: Saw bass  V3: Tri arp" << std::endl;
    std::cout << "Filter: Dynamic LP sweep (600→5000→400 Hz)"  << std::endl;
    std::cout << "Duration: " << DURATION << "s (" << max_samples << " samples)" << std::endl;
    std::cout << "PDM output: 10 MHz, 1-bit, packed binary" << std::endl;

    // ── Enable PDM capture ──────────────────────────────────────────────────────
    g_tick_count = 0;
    g_pdm_active = true;

    // ── Main Sample Loop ────────────────────────────────────────────────────────
    size_t event_idx  = 0;
    size_t filt_idx   = 0;

    while (total_samples < max_samples) {
        // Process all note events scheduled for this sample
        while (event_idx < song.size() && song[event_idx].sample <= total_samples) {
            auto& ev = song[event_idx];
            switch (ev.type) {
                case EventType::GATE_ON:
                    set_voice_freq(contextp, top, ev.voice, ev.freq);
                    set_control(contextp, top, ev.voice, ev.wave, true);
                    break;
                case EventType::GATE_OFF:
                    set_control(contextp, top, ev.voice, ev.wave, false);
                    break;
                case EventType::FREQ_ONLY:
                    set_voice_freq(contextp, top, ev.voice, ev.freq);
                    break;
            }
            event_idx++;
        }

        // Process all filter events scheduled for this sample
        while (filt_idx < filter_song.size() && filter_song[filt_idx].sample <= total_samples) {
            auto& fe = filter_song[filt_idx];
            set_filter(contextp, top, fe.fc, fe.q, fe.en_mode);
            filt_idx++;
        }

        tick_batch(contextp, top, TICKS_PER_SAMPLE);
        total_samples++;

        if (total_samples % SAMPLE_RATE == 0) {
            std::cout << "Time: " << (total_samples / SAMPLE_RATE)
                      << "s / " << (int)DURATION << "s" << std::endl;
        }
    }

    // Flush remaining PDM bits (pad with zeros)
    if (g_pdm_bit_count > 0) {
        g_pdm_byte <<= (8 - g_pdm_bit_count);
        g_pdm_file.put(static_cast<char>(g_pdm_byte));
    }
    g_pdm_file.close();

    top->final();

    std::cout << "PDM samples captured: " << g_pdm_total
              << " (" << (double)g_pdm_total / PDM_RATE_HZ << "s at "
              << PDM_RATE_HZ / 1000000 << " MHz)" << std::endl;
    std::cout << "Saved to pdm_output.bin ("
              << (g_pdm_total + 7) / 8 << " bytes)" << std::endl;
    return 0;
}