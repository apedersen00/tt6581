//-------------------------------------------------------------------------------------------------
//
//  File: sim_common.h
//  Description: Common utilities for all TT6581 testbenches.
//
//  Author:
//    - Andreas Pedersen
//
//-------------------------------------------------------------------------------------------------

#ifndef SIM_COMMON_H
#define SIM_COMMON_H

#include <memory>
#include <iostream>
#include <fstream>
#include <cmath>
#include <cstdint>
#include <string>
#include <verilated.h>

//=============================================================================
// Clock and Timing
//=============================================================================
#define CLK_PERIOD_NS     20                                // 50 MHz system clock period (ns)
#define CLK_FREQ_HZ       50000000ULL                       // 50 MHz system clock frequency
#define SAMPLE_RATE_HZ    50000ULL                          // 50 kHz audio sample rate
#define CYCLES_PER_SAMPLE (CLK_FREQ_HZ / SAMPLE_RATE_HZ)    // 1000 system clocks per audio sample
#define DAC_RATE_HZ       10000000ULL                       // 10 MHz PDM DAC rate
#define CYCLES_PER_DAC    (CLK_FREQ_HZ / DAC_RATE_HZ)       // 5 system clocks per DAC sample

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

//=============================================================================
// Voice Base Registers and Offsets
//=============================================================================
#define V1_BASE 0x00
#define V2_BASE 0x07
#define V3_BASE 0x0E

#define REG_FREQ_LO 0x00
#define REG_FREQ_HI 0x01
#define REG_PW_LO   0x02
#define REG_PW_HI   0x03
#define REG_CTRL    0x04
#define REG_AD      0x05
#define REG_SR      0x06

//=============================================================================
// Filter Base Registers and Offsets
//=============================================================================
#define FILT_BASE   0x15
#define REG_F_LO    0x00
#define REG_F_HI    0x01
#define REG_Q_LO    0x02
#define REG_Q_HI    0x03
#define REG_EN_MODE 0x04
#define REG_VOLUME  0x05

//=============================================================================
// Filter Mode Bits
//=============================================================================
#define FILT_LP 0x01
#define FILT_BP 0x02
#define FILT_HP 0x04

//=============================================================================
// Voice Filter Enable Bits
//=============================================================================
#define FILT_V1 0x08
#define FILT_V2 0x10
#define FILT_V3 0x20

//=============================================================================
// Voice Waveform Bits
//=============================================================================
#define WAVE_TRI   0x10
#define WAVE_SAW   0x20
#define WAVE_PULSE 0x40

//=============================================================================
// Utility Functions
//=============================================================================

/**
 * @brief Perform one full system clock cycle (rising + falling edge).
 *
 * @tparam T    Verilator model type (e.g. Vtb_mult, Vtb_tt6581).
 * @param ctx   Verilator simulation context.
 * @param top   Pointer to the Verilator top-level model instance.
 */
template <typename T>
void tick(const std::unique_ptr<VerilatedContext>& ctx,
          const std::unique_ptr<T>& top) {
    top->clk_i = 0;
    top->eval();
    ctx->timeInc(CLK_PERIOD_NS / 2);
    top->clk_i = 1;
    top->eval();
    ctx->timeInc(CLK_PERIOD_NS / 2);
}

/**
 * @brief Run multiple system clock cycles.
 *
 * @tparam T    Verilator model type (e.g. Vtb_mult, Vtb_tt6581).
 * @param ctx   Verilator simulation context.
 * @param top   Pointer to the Verilator top-level model instance.
 * @param ticks Number of full clock cycles to execute.
 */
template <typename T>
void tick_batch(const std::unique_ptr<VerilatedContext>& ctx,
                const std::unique_ptr<T>& top,
                uint64_t ticks) {
    for (uint64_t i = 0; i < ticks; i++) {
        tick(ctx, top);
    }
}

/**
 * @brief PDM capture.
 *
 * Packs 1-bit PDM samples into bytes and streams them to a binary file.
 */
struct PdmCapture {
    std::ofstream file;
    uint8_t  byte      = 0;
    int      bit_count = 0;
    uint64_t total     = 0;
    bool     active    = false;

    /**
     * @brief Open the output binary file.
     * @param path  File path to write PDM data to.
     */
    void open(const std::string& path) {
        file.open(path, std::ios::binary);
    }

    /**
     * @brief Capture a single 1-bit PDM sample.
     *
     * @param pdm_bit  The 1-bit PDM sample.
     */
    void capture(uint8_t pdm_bit) {
        byte = (byte << 1) | (pdm_bit & 1);
        bit_count++;
        if (bit_count == 8) {
            file.put(static_cast<char>(byte));
            byte = 0;
            bit_count = 0;
        }
        total++;
    }

    /**
     * @brief Flush any remaining bits and close the file.
     */
    void flush() {
        if (bit_count > 0) {
            byte <<= (8 - bit_count);
            file.put(static_cast<char>(byte));
        }
        file.close();
    }
};

/**
 * @brief Write one register over SPI.
 *
 * @tparam T       Verilator model type (e.g. Vtb_mult, Vtb_tt6581).
 * @param top      Pointer to the Verilator top-level model instance.
 * @param tick_fn  Tick function.
 * @param addr     7-bit register address.
 * @param data     8-bit data to write.
 * @param spi_div  SPI clock divider (system clocks per SPI half-period).
 */
template <typename T, typename TickFn>
void spi_write(const std::unique_ptr<T>& top, TickFn tick_fn,
               uint8_t addr, uint8_t data, int spi_div = 20) {
    uint16_t frame = 0x8000 | (addr << 8) | data;
    top->cs_i = 0;
    for (int i = 15; i >= 0; i--) {
        top->mosi_i = (frame >> i) & 1;
        for (int k = 0; k < spi_div / 2; k++) tick_fn();
        top->sclk_i = 1;
        for (int k = 0; k < spi_div / 2; k++) tick_fn();
        top->sclk_i = 0;
    }
    for (int k = 0; k < spi_div / 2; k++) tick_fn();
    top->cs_i = 1;
    for (int k = 0; k < 20; k++) tick_fn();
}

/**
 * @brief Compute the SVF frequency cutoff coefficient (Q1.15 fixed-point).
 *
 * coeff = 2 * sin(pi * fc / Fs) * 2^15
 *
 * @param fc  Desired cutoff frequency in Hz.
 * @return    16-bit signed fixed-point coefficient.
 */
inline int16_t get_coeff_f(double fc) {
    double f = 2.0 * std::sin(M_PI * fc / SAMPLE_RATE_HZ);
    return (int16_t)(f * 32768.0);
}

/**
 * @brief Compute the SVF damping/resonance coefficient (Q4.12 fixed-point).
 *
 * coeff = (1/Q) * 2^12
 *
 * @param q  Desired Q factor.
 * @return   16-bit signed fixed-point coefficient.
 */
inline int16_t get_coeff_q(double q) {
    double q_damp = 1.0 / q;
    return (int16_t)(q_damp * 4096.0);
}

/**
 * @brief Compute the 16-bit Frequency Control Word (FCW) for a voice.
 *
 * FCW = freq * 2^19 / Fs
 *
 * @param freq  Desired frequency in Hz.
 * @return      16-bit unsigned FCW to be written to FREQ_LO / FREQ_HI.
 */
inline uint16_t calc_fcw(double freq) {
    uint64_t numerator = (uint64_t)freq * (1ULL << 19);
    return (uint16_t)(numerator / SAMPLE_RATE_HZ);
}

/**
 * @brief Set a voice's oscillator frequency via SPI.
 *
 * Computes the FCW and writes it to FREQ_LO and FREQ_HI.
 *
 * @tparam T        Verilator model type (e.g. Vtb_mult, Vtb_tt6581).
 * @param top       Pointer to the Verilator top-level model instance.
 * @param tick_fn   Tick function.
 * @param base_addr Voice base register address.
 * @param freq      Desired frequency in Hz.
 */
template <typename T, typename TickFn>
void set_voice_freq(const std::unique_ptr<T>& top, TickFn tick_fn,
                    uint8_t base_addr, double freq) {
    uint16_t fcw = calc_fcw(freq);
    spi_write(top, tick_fn, base_addr + REG_FREQ_LO, fcw & 0xFF);
    spi_write(top, tick_fn, base_addr + REG_FREQ_HI, (fcw >> 8) & 0xFF);
}

/**
 * @brief Configure a voice's pulse width (50%) and waveform via SPI.
 *
 * Sets PW to 0x0800 (50% duty) and writes the waveform control byte.
 *
 * @tparam T            Verilator model type (e.g. Vtb_mult, Vtb_tt6581).
 * @param top           Pointer to the Verilator top-level model instance.
 * @param tick_fn       Tick function.
 * @param base_addr     Voice base register address.
 * @param wave_ctrl     Waveform control byte (e.g. WAVE_TRI | 0x01 for gate).
 */
template <typename T, typename TickFn>
void setup_voice(const std::unique_ptr<T>& top, TickFn tick_fn,
                 uint8_t base_addr, uint8_t wave_ctrl) {
    spi_write(top, tick_fn, base_addr + REG_PW_LO, 0x00);
    spi_write(top, tick_fn, base_addr + REG_PW_HI, 0x08);
    spi_write(top, tick_fn, base_addr + REG_CTRL, wave_ctrl);
}

/**
 * @brief Set a voice's ADSR envelope parameters via SPI.
 *
 * @tparam T            Verilator model type (e.g. Vtb_mult, Vtb_tt6581).
 * @param top           Pointer to the Verilator top-level model instance.
 * @param tick_fn       Tick function.
 * @param base_addr     Voice base register address.
 * @param attack        Attack rate (4-bit, 0-15).
 * @param decay         Decay rate (4-bit, 0-15).
 * @param sustain       Sustain level (4-bit, 0-15).
 * @param release       Release rate (4-bit, 0-15).
 */
template <typename T, typename TickFn>
void set_adsr(const std::unique_ptr<T>& top, TickFn tick_fn,
              uint8_t base_addr,
              uint8_t attack, uint8_t decay,
              uint8_t sustain, uint8_t release) {
    uint8_t ad = ((attack & 0x0F) << 4) | (decay & 0x0F);
    uint8_t sr = ((sustain & 0x0F) << 4) | (release & 0x0F);
    spi_write(top, tick_fn, base_addr + REG_AD, ad);
    spi_write(top, tick_fn, base_addr + REG_SR, sr);
}

/**
 * @brief Set a voice's waveform and gate bit via SPI.
 *
 * @tparam T                Verilator model type (e.g. Vtb_mult, Vtb_tt6581).
 * @param top               Pointer to the Verilator top-level model instance.
 * @param tick_fn           Tick function.
 * @param base_addr         Voice base register address.
 * @param waveform_mask     Waveform bits.
 * @param gate              true = gate on, false = gate off.
 */
template <typename T, typename TickFn>
void set_control(const std::unique_ptr<T>& top, TickFn tick_fn,
                 uint8_t base_addr,
                 uint8_t waveform_mask, bool gate) {
    uint8_t ctrl = waveform_mask;
    if (gate) ctrl |= 0x01;
    spi_write(top, tick_fn, base_addr + REG_CTRL, ctrl);
}

/**
 * @brief Configure the SVF filter parameters via SPI.
 *
 * Computes the fixed-point coefficients from fc and q, then writes
 * F_LO, F_HI, Q_LO, Q_HI, and EN_MODE.
 *
 * @tparam T       Verilator model type (e.g. Vtb_mult, Vtb_tt6581)..
 * @param top      Pointer to the Verilator top-level model instance.
 * @param tick_fn  Tick function.
 * @param fc       Filter cutoff frequency in Hz.
 * @param q        Filter Q factor.
 * @param en_mode  Combined filter-enable and mode byte (e.g.
 *                 FILT_V1 | FILT_LP to route Voice 0 through low-pass).
 */
template <typename T, typename TickFn>
void set_filter(const std::unique_ptr<T>& top, TickFn tick_fn,
                double fc, double q, uint8_t en_mode) {
    int16_t cf = get_coeff_f(fc);
    int16_t cq = get_coeff_q(q);
    spi_write(top, tick_fn, FILT_BASE + REG_F_LO, cf & 0xFF);
    spi_write(top, tick_fn, FILT_BASE + REG_F_HI, (cf >> 8) & 0xFF);
    spi_write(top, tick_fn, FILT_BASE + REG_Q_LO, cq & 0xFF);
    spi_write(top, tick_fn, FILT_BASE + REG_Q_HI, (cq >> 8) & 0xFF);
    spi_write(top, tick_fn, FILT_BASE + REG_EN_MODE, en_mode);
}

#endif // SIM_COMMON_H
