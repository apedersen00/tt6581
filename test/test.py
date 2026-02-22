# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

"""
CocoTB tests for the TT6581.
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

from tt6581_tb import (
    # constants
    V0_BASE, V1_BASE, V2_BASE, WAVE_TRI, WAVE_SAW, WAVE_PULSE, WAVE_NOISE, WAVEFORM_NAMES,
    # voice helpers
    setup_voice, gate_on, gate_off, set_volume,
    # signal / capture
    reset_dut, capture_audio,
    # plotting
    plot_audio_samples, plot_frequencies, plot_envelope
)


# =============================================================================
#  Tests
# =============================================================================

# @cocotb.test()
async def test_waveforms(dut):
    """
    Play all four waveforms at 1000 Hz and plot them.
    """

    dut._log.info("=== test_waveforms: start ===")

    clock = Clock(dut.clk, 20, unit="ns")   # 50 MHz
    cocotb.start_soon(clock.start())
    await reset_dut(dut)
    await set_volume(dut, 0xFF)             # Max volume

    for wave_mask, wave_name in WAVEFORM_NAMES.items():
        dut._log.info(f"*** {wave_name} ***")

        # Program voice
        await setup_voice(dut, V0_BASE, freq_hz=1000.0,
                          waveform=wave_mask, pw=0x800,
                          attack=0, decay=0, sustain=0xF, release=0)
        await gate_on(dut, V0_BASE, wave_mask)

        # Let the envelope reach sustain before capturing
        await ClockCycles(dut.clk, 500000)

        samples = await capture_audio(dut, num_samples=500)
        dut._log.info(f"[TB] Captured {len(samples)} samples for {wave_name}")

        plot_audio_samples(
            samples,
            filename=f"wave_{wave_name.lower()}.png",
            title=f"audio_i — Voice 0 {wave_name} 1000 Hz",
        )

        # Gate off + settle before next waveform
        await gate_off(dut, V0_BASE, wave_mask)
        await ClockCycles(dut.clk, 5000)

    dut._log.info("=== test_waveforms: done ===")

# @cocotb.test()
async def test_frequencies(dut):
    """
    Play three voices at different frequencies and calculate frequency spectrum.
    """

    dut._log.info("=== test_frequencies: start ===")

    clock = Clock(dut.clk, 20, unit="ns")   # 50 MHz
    cocotb.start_soon(clock.start())
    await reset_dut(dut)
    await set_volume(dut, 0xFF)             # Max volume

    freqs = [
        [100, 1000, 5000],
        [50, 200, 400] 
    ]

    for i, f in enumerate(freqs):
        dut._log.info(f"*** {f} ***")

        # Program voices
        await setup_voice(dut, V0_BASE, freq_hz=f[0],
                          waveform=WAVE_TRI, pw=0x800,
                          attack=0, decay=0, sustain=0xF, release=0)
        await gate_on(dut, V0_BASE, WAVE_TRI)

        await setup_voice(dut, V1_BASE, freq_hz=f[1],
                          waveform=WAVE_TRI, pw=0x800,
                          attack=0, decay=0, sustain=0xF, release=0)
        await gate_on(dut, V1_BASE, WAVE_TRI)

        await setup_voice(dut, V2_BASE, freq_hz=f[2],
                          waveform=WAVE_TRI, pw=0x800,
                          attack=0, decay=0, sustain=0xF, release=0)
        await gate_on(dut, V2_BASE, WAVE_TRI)

        # Let the envelope reach sustain before capturing
        await ClockCycles(dut.clk, 500000)

        samples = await capture_audio(dut, num_samples=5000)
        dut._log.info(f"[TB] Captured {len(samples)} samples for frequencies: {f}")

        stats = plot_frequencies(
            samples,
            expected_freqs=f,
            filename=f"wave_freq_{i}.png",
            title=f"audio_i — expected {f[0]:.0f} / {f[1]:.0f} / {f[2]:.0f} Hz",
        )
        dut._log.info(
            f"[TB] Detected peaks: "
            + ", ".join(f"{d:.1f} Hz" for d in stats['detected_freqs'])
        )

        # Gate off + settle before next waveform
        await gate_off(dut, V0_BASE, WAVE_TRI)
        await gate_off(dut, V1_BASE, WAVE_TRI)
        await gate_off(dut, V2_BASE, WAVE_TRI)
        await ClockCycles(dut.clk, 5000)

    dut._log.info("=== test_frequencies: done ===")

@cocotb.test()
async def test_envelopes(dut):
    """Test different ADSR envelope settings with a sawtooth and plot the
    amplitude envelope over time."""

    dut._log.info("=== test_envelopes: start ===")

    clock = Clock(dut.clk, 20, unit="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)
    await set_volume(dut, 0xFF)

    # Each entry: (label, attack, decay, sustain, release, gate_on_samples, gate_off_samples)
    envelope_configs = [
        ("A0 D0 S15 R0  (instant)",     0,  0, 0xF,  0,  50*20,  50*12),   # 2ms, 6ms, 6ms
        ("A4 D4 S10 R4  (moderate)",    4,  4, 0xA,  4,  50*150,  50*120), # 38ms, 114m, 114ms
        #("A8 D6 S8  R8  (slow)",        8,  6, 0x8,  8,  500,  500),
        #("A0 D0 S15 R15 (long release)",0,  0, 0xF, 0xF, 500,  500),
        #("A15 D0 S15 R0 (slow attack)", 0xF,0, 0xF,  0,  500,  500),
    ]

    all_traces: list[tuple[str, list[int]]] = []

    for label, atk, dec, sus, rel, gate_samps, rel_samps in envelope_configs:
        dut._log.info(f"*** Envelope: {label} ***")

        await setup_voice(dut, V0_BASE, freq_hz=2000.0,
                          waveform=WAVE_SAW, pw=0x800,
                          attack=atk, decay=dec,
                          sustain=sus, release=rel)

        # Gate ON — capture attack/decay/sustain phase
        await gate_on(dut, V0_BASE, WAVE_SAW)
        on_samples = await capture_audio(dut, num_samples=gate_samps)

        # Gate OFF — capture release phase
        await gate_off(dut, V0_BASE, WAVE_SAW)
        off_samples = await capture_audio(dut, num_samples=rel_samps)

        combined = on_samples + off_samples
        dut._log.info(f"  Captured {len(combined)} samples "
                      f"({len(on_samples)} on + {len(off_samples)} off)")

        safe_name = label.split("(")[0].strip().replace(" ", "_")
        plot_envelope(
            combined, atk, dec, sus, rel, gate_samps,
            filename=f"env_{safe_name}.png",
            title=f"audio_i — Envelope: {label}",
        )

        all_traces.append((label, combined))

        # Small settle gap
        await ClockCycles(dut.clk, 5000)

    dut._log.info("=== test_envelopes: done ===")
