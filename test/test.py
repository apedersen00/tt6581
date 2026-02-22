# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

"""CocoTB tests for the TT6581 SID clone.

All helpers live in the ``tt6581_tb`` package; this file only contains
the @cocotb.test() entry-points.
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

from tt6581_tb import (
    # constants
    V0_BASE, WAVE_TRI, WAVE_SAW, WAVE_PULSE, WAVE_NOISE, WAVEFORM_NAMES,
    # voice helpers
    setup_voice, gate_on, gate_off, set_volume,
    # signal / capture
    reset_dut, capture_audio,
    # plotting
    plot_audio_samples, plot_multi_overlay,
)


# =============================================================================
#  Tests
# =============================================================================

@cocotb.test()
async def test_waveforms(dut):
    """Sweep all four waveform types at 1000 Hz and plot each one,
    plus an overlay comparison."""

    dut._log.info("=== test_waveforms: start ===")

    clock = Clock(dut.clk, 20, unit="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)
    await set_volume(dut, 0xFF)

    all_traces: list[tuple[str, list[int]]] = []

    for wave_mask, wave_name in WAVEFORM_NAMES.items():
        dut._log.info(f"── {wave_name} ──")

        # Reset the voice fully before each waveform
        await setup_voice(dut, V0_BASE, freq_hz=1000.0,
                          waveform=wave_mask, pw=0x800,
                          attack=0, decay=0, sustain=0xF, release=0)
        await gate_on(dut, V0_BASE, wave_mask)

        # Let the envelope reach sustain before capturing
        await ClockCycles(dut.clk, 5000)

        samples = await capture_audio(dut, num_samples=500)
        dut._log.info(f"  Captured {len(samples)} samples for {wave_name}")

        # Individual plot
        plot_audio_samples(
            samples,
            filename=f"wave_{wave_name.lower()}.png",
            title=f"audio_i — {wave_name} 1000 Hz",
        )

        all_traces.append((wave_name, samples))

        # Gate off + settle before next waveform
        await gate_off(dut, V0_BASE, wave_mask)
        await ClockCycles(dut.clk, 5000)

    # Overlay all waveforms
    plot_multi_overlay(
        all_traces,
        filename="wave_overlay.png",
        title="audio_i — All Waveforms @ 1000 Hz",
    )

    dut._log.info("=== test_waveforms: done ===")


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
        ("A0 D0 S15 R0  (instant)",     0,  0, 0xF,  0,  300,  200),
        ("A4 D4 S10 R4  (moderate)",    4,  4, 0xA,  4,  400,  300),
        ("A8 D6 S8  R8  (slow)",        8,  6, 0x8,  8,  500,  500),
        ("A0 D0 S15 R15 (long release)",0,  0, 0xF, 0xF, 200,  600),
        ("A15 D0 S15 R0 (slow attack)", 0xF,0, 0xF,  0,  800,  200),
    ]

    all_traces: list[tuple[str, list[int]]] = []

    for label, atk, dec, sus, rel, gate_samps, rel_samps in envelope_configs:
        dut._log.info(f"── Envelope: {label} ──")

        await setup_voice(dut, V0_BASE, freq_hz=440.0,
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
        plot_audio_samples(
            combined,
            filename=f"env_{safe_name}.png",
            title=f"audio_i — Envelope: {label}",
        )

        all_traces.append((label, combined))

        # Small settle gap
        await ClockCycles(dut.clk, 5000)

    # Overlay all envelopes
    plot_multi_overlay(
        all_traces,
        filename="env_overlay.png",
        title="audio_i — Envelope Comparison (Sawtooth 440 Hz)",
    )

    dut._log.info("=== test_envelopes: done ===")
