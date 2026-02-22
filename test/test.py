# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import math
import os

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, FallingEdge, Timer

# Output directory for all testbench products (plots, CSVs)
TB_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "tmp")
os.makedirs(TB_OUTPUT_DIR, exist_ok=True)


# =============================================================================
#  Constants
# =============================================================================

SPI_FREQ_NS = 200           # Half-period of SPI clock (keep well below 50 MHz sys clk)
SYS_CLK_HZ  = 50_000_000
SAMPLE_RATE = 50_000       # Internal sample rate driven by tick_gen

# ── Per-voice register offsets (relative to voice base) ──────────────────────
REG_FREQ_LO  = 0x00
REG_FREQ_HI  = 0x01
REG_PW_LO    = 0x02
REG_PW_HI    = 0x03
REG_CTRL     = 0x04
REG_AD       = 0x05
REG_SR       = 0x06

# ── Voice base addresses ────────────────────────────────────────────────────
V0_BASE = 0x00
V1_BASE = 0x07
V2_BASE = 0x0E

# ── Filter registers (absolute) ─────────────────────────────────────────────
FILT_BASE      = 0x15
REG_FILT_F_LO  = FILT_BASE + 0x00   # 0x15
REG_FILT_F_HI  = FILT_BASE + 0x01   # 0x16
REG_FILT_Q_LO  = FILT_BASE + 0x02   # 0x17
REG_FILT_Q_HI  = FILT_BASE + 0x03   # 0x18
REG_FILT_ENMOD = FILT_BASE + 0x04   # 0x19
REG_FILT_VOL   = FILT_BASE + 0x05   # 0x1A

# ── Waveform select masks (upper nibble of CTRL) ────────────────────────────
WAVE_TRI   = 0x10
WAVE_SAW   = 0x20
WAVE_PULSE = 0x40
WAVE_NOISE = 0x80

# ── Filter mode bits (EN_MODE[2:0]) ─────────────────────────────────────────
FILT_LP = 0x01
FILT_BP = 0x02
FILT_HP = 0x04

# ── Voice filter-enable bits (EN_MODE[5:3]) ─────────────────────────────────
FILT_V0 = 0x08
FILT_V1 = 0x10
FILT_V2 = 0x20

# ── Note frequencies (Hz) ───────────────────────────────────────────────────
NOTE_FREQ = {
    "C2": 65.41,  "D2": 73.42,  "Eb2": 77.78,  "F2": 87.31,
    "G2": 98.00,  "Ab2": 103.83, "Bb2": 116.54, "B2": 123.47,
    "C3": 130.81, "D3": 146.83, "Eb3": 155.56, "F3": 174.61,
    "G3": 196.00, "Ab3": 207.65, "Bb3": 233.08, "B3": 246.94,
    "C4": 261.63, "D4": 293.66, "Eb4": 311.13, "F4": 349.23,
    "G4": 392.00, "Ab4": 415.30, "Bb4": 466.16, "B4": 493.88,
    "C5": 523.25, "D5": 587.33, "Eb5": 622.25, "G5": 783.99,
}

# =============================================================================
#  Low-level SPI driver
# =============================================================================

async def spi_write(dut, addr: int, data: int):
    """Write an 8-bit value to a 7-bit register address over SPI.

    Frame: [1(write) | addr(7) | data(8)], MSB first.
    Drives ui_in[0] (sclk), ui_in[1] (cs), ui_in[2] (mosi).
    """
    word = (1 << 15) | ((addr & 0x7F) << 8) | (data & 0xFF)
    base = int(dut.ui_in.value) & ~0x07

    # Assert CS (low)
    dut.ui_in.value = base | 0x00
    await Timer(SPI_FREQ_NS, unit="ns")

    # Shift out MSB first
    for i in range(15, -1, -1):
        bit = (word >> i) & 1
        dut.ui_in.value = base | (bit << 2) | 0x00   # cs=0, sclk=0
        await Timer(SPI_FREQ_NS, unit="ns")
        dut.ui_in.value = base | (bit << 2) | 0x01   # cs=0, sclk=1
        await Timer(SPI_FREQ_NS, unit="ns")

    # SCLK back low
    dut.ui_in.value = base | 0x00
    await Timer(SPI_FREQ_NS, unit="ns")

    # Deassert CS (high)
    dut.ui_in.value = base | 0x02
    await Timer(SPI_FREQ_NS, unit="ns")


async def spi_read(dut, addr: int) -> int:
    """Read an 8-bit value from a 7-bit register address over SPI.

    Frame: [0(read) | addr(7) | 0x00], MSB first.
    Returns the byte sampled on uo_out[0] (MISO) during the data phase.
    """
    word = ((addr & 0x7F) << 8) | 0x00
    base = int(dut.ui_in.value) & ~0x07

    dut.ui_in.value = base | 0x00
    await Timer(SPI_FREQ_NS, unit="ns")

    read_val = 0
    for i in range(15, -1, -1):
        bit = (word >> i) & 1
        dut.ui_in.value = base | (bit << 2) | 0x00
        await Timer(SPI_FREQ_NS, unit="ns")
        dut.ui_in.value = base | (bit << 2) | 0x01
        await Timer(SPI_FREQ_NS, unit="ns")
        if i <= 7:
            miso_bit = int(dut.uo_out.value) & 0x01
            read_val = (read_val << 1) | miso_bit

    dut.ui_in.value = base | 0x00
    await Timer(SPI_FREQ_NS, unit="ns")
    dut.ui_in.value = base | 0x02
    await Timer(SPI_FREQ_NS, unit="ns")

    return read_val


# =============================================================================
#  Frequency / filter coefficient helpers
# =============================================================================

def calc_fcw(freq_hz: float) -> int:
    """Compute the 16-bit frequency control word.

    FCW = freq * 2^19 / 50000   (matches Verilator testbench)
    """
    return int(freq_hz * (1 << 19) / SAMPLE_RATE)


def get_coeff_f(fc_hz: float) -> int:
    """Compute the signed 16-bit (Q1.15) filter cutoff coefficient.

    f = 2 * sin(pi * fc / Fs)  scaled to Q1.15
    """
    f = 2.0 * math.sin(math.pi * fc_hz / SAMPLE_RATE)
    val = int(f * 32768.0)
    # Clamp to signed 16-bit range
    val = max(-32768, min(32767, val))
    return val & 0xFFFF


def get_coeff_q(q: float) -> int:
    """Compute the signed 16-bit (Q4.12) filter resonance (damping) coefficient.

    q_damp = 1/Q  scaled to Q4.12
    """
    q_damp = 1.0 / q
    val = int(q_damp * 4096.0)
    val = max(-32768, min(32767, val))
    return val & 0xFFFF


# =============================================================================
#  Voice programming helpers
# =============================================================================

async def set_voice_freq(dut, voice_base: int, freq_hz: float):
    """Program the frequency control word for a voice."""
    fcw = calc_fcw(freq_hz)
    await spi_write(dut, voice_base + REG_FREQ_LO, fcw & 0xFF)
    await spi_write(dut, voice_base + REG_FREQ_HI, (fcw >> 8) & 0xFF)


async def set_voice_pw(dut, voice_base: int, pw: int):
    """Program the 12-bit pulse width for a voice (0x000 – 0xFFF)."""
    await spi_write(dut, voice_base + REG_PW_LO, pw & 0xFF)
    await spi_write(dut, voice_base + REG_PW_HI, (pw >> 8) & 0x0F)


async def set_voice_adsr(dut, voice_base: int,
                         attack: int, decay: int,
                         sustain: int, release: int):
    """Program attack/decay/sustain/release (4-bit each) for a voice."""
    ad = ((attack & 0x0F) << 4) | (decay & 0x0F)
    sr = ((sustain & 0x0F) << 4) | (release & 0x0F)
    await spi_write(dut, voice_base + REG_AD, ad)
    await spi_write(dut, voice_base + REG_SR, sr)


async def set_voice_control(dut, voice_base: int,
                            waveform: int, gate: bool,
                            ring_mod: bool = False, sync: bool = False):
    """Program the voice control register.

    waveform: WAVE_TRI / WAVE_SAW / WAVE_PULSE / WAVE_NOISE (or OR-ed combo)
    gate:     True = start envelope attack, False = release
    """
    ctrl = waveform & 0xFE
    if gate:
        ctrl |= 0x01
    if sync:
        ctrl |= 0x02
    if ring_mod:
        ctrl |= 0x04
    await spi_write(dut, voice_base + REG_CTRL, ctrl)


async def setup_voice(dut, voice_base: int, freq_hz: float,
                      waveform: int, pw: int = 0x800,
                      attack: int = 0, decay: int = 6,
                      sustain: int = 0xF, release: int = 6):
    """Convenience: fully configure a voice (freq + PW + ADSR) in one call.

    Does NOT gate the voice — call set_voice_control() afterwards.
    """
    await set_voice_freq(dut, voice_base, freq_hz)
    await set_voice_pw(dut, voice_base, pw)
    await set_voice_adsr(dut, voice_base, attack, decay, sustain, release)


async def gate_on(dut, voice_base: int, waveform: int,
                  ring_mod: bool = False, sync: bool = False):
    """Open the gate (start attack phase)."""
    await set_voice_control(dut, voice_base, waveform, gate=True,
                            ring_mod=ring_mod, sync=sync)


async def gate_off(dut, voice_base: int, waveform: int):
    """Close the gate (start release phase)."""
    await set_voice_control(dut, voice_base, waveform, gate=False)


# =============================================================================
#  Filter programming helpers
# =============================================================================

async def set_filter(dut, fc_hz: float, q: float, en_mode: int):
    """Program the filter cutoff, resonance and routing/mode register.

    fc_hz:   cutoff frequency in Hz
    q:       resonance Q factor (≥ 0.5 typ.)
    en_mode: OR of FILT_V0/V1/V2 (voice routing) | FILT_LP/BP/HP (mode)
    """
    cf = get_coeff_f(fc_hz)
    cq = get_coeff_q(q)
    await spi_write(dut, REG_FILT_F_LO, cf & 0xFF)
    await spi_write(dut, REG_FILT_F_HI, (cf >> 8) & 0xFF)
    await spi_write(dut, REG_FILT_Q_LO, cq & 0xFF)
    await spi_write(dut, REG_FILT_Q_HI, (cq >> 8) & 0xFF)
    await spi_write(dut, REG_FILT_ENMOD, en_mode)


async def set_filter_cutoff(dut, fc_hz: float):
    """Update only the filter cutoff frequency."""
    cf = get_coeff_f(fc_hz)
    await spi_write(dut, REG_FILT_F_LO, cf & 0xFF)
    await spi_write(dut, REG_FILT_F_HI, (cf >> 8) & 0xFF)


async def set_filter_q(dut, q: float):
    """Update only the filter resonance."""
    cq = get_coeff_q(q)
    await spi_write(dut, REG_FILT_Q_LO, cq & 0xFF)
    await spi_write(dut, REG_FILT_Q_HI, (cq >> 8) & 0xFF)


async def set_volume(dut, vol: int):
    """Set the master volume register (0x00 – 0xFF)."""
    await spi_write(dut, REG_FILT_VOL, vol & 0xFF)


# =============================================================================
#  Signal accessors — read internal RTL signals
# =============================================================================

def _sid(dut):
    """Shortcut to the tt6581 instance inside the TT wrapper."""
    return dut.tt6581.tt6581_inst


def get_audio_pre_ds(dut) -> int:
    """Return the signed 14-bit value feeding the delta-sigma modulator (mult_out)."""
    return _sid(dut).mult_out.value.to_signed()


def get_bypass_accum(dut) -> int:
    """Return the signed 14-bit bypass (unfiltered) accumulator."""
    return _sid(dut).bypass_accum.value.to_signed()


def get_filter_accum(dut) -> int:
    """Return the signed 14-bit filter accumulator."""
    return _sid(dut).filter_accum.value.to_signed()


def get_audio_valid(dut) -> bool:
    """Return True when audio_valid is asserted (new sample ready)."""
    return bool(_sid(dut).audio_valid.value)


def get_ds_audio_i(dut) -> int:
    """Return the signed 14-bit audio_i inside the delta-sigma module."""
    return _sid(dut).delta_sigma_inst.audio_i.value.to_signed()


def get_ds_audio_valid(dut) -> bool:
    """Return the audio_valid_i flag inside the delta-sigma module."""
    return bool(_sid(dut).delta_sigma_inst.audio_valid_i.value)


def get_wave_o(dut) -> int:
    """Return the 1-bit PDM output."""
    return int(_sid(dut).delta_sigma_inst.wave_o.value)


# =============================================================================
#  Reset helper
# =============================================================================

async def reset_dut(dut, cycles: int = 10):
    """Assert reset for *cycles* clocks, then deassert and settle."""
    dut.ena.value = 1
    dut.ui_in.value = 0x02   # cs=1 (deasserted), sclk=0, mosi=0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, cycles)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, cycles)


# =============================================================================
#  Plotting / CSV helpers
# =============================================================================

def plot_audio_samples(samples: list[int], filename: str = "audio_i_plot.png",
                       title: str = "delta_sigma.audio_i",
                       sample_rate: int = SAMPLE_RATE):
    """Save a time-domain plot of captured 14-bit signed audio samples as PNG.

    X-axis is time in milliseconds.  Also writes a companion CSV.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import csv

    # Time axis in ms
    t_ms = [i / sample_rate * 1000.0 for i in range(len(samples))]

    # ── Write CSV ────────────────────────────────────────────────────────────
    csv_path = os.path.join(TB_OUTPUT_DIR, filename.rsplit(".", 1)[0] + ".csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time_ms", "audio_i"])
        for t, v in zip(t_ms, samples):
            writer.writerow([f"{t:.6f}", v])

    # ── Plot ─────────────────────────────────────────────────────────────────
    plot_path = os.path.join(TB_OUTPUT_DIR, filename)
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(t_ms, samples, linewidth=0.6)
    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("audio_i  (signed 14-bit)")
    ax.set_title(title)
    ax.set_ylim(-1024, 1023)
    ax.axhline(0, color="grey", linewidth=0.3)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)


def plot_multi_overlay(all_traces: list[tuple[str, list[int]]],
                       filename: str, title: str,
                       sample_rate: int = SAMPLE_RATE):
    """Plot multiple sample traces overlaid on the same axes."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(14, 5))
    for label, samples in all_traces:
        t_ms = [i / sample_rate * 1000.0 for i in range(len(samples))]
        ax.plot(t_ms, samples, linewidth=0.6, label=label)
    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("audio_i  (signed 14-bit)")
    ax.set_title(title)
    ax.set_ylim(-1024, 1023)
    ax.axhline(0, color="grey", linewidth=0.3)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(TB_OUTPUT_DIR, filename), dpi=150)
    plt.close(fig)


# =============================================================================
#  Reusable capture routine
# =============================================================================

async def capture_audio(dut, num_samples: int = 500,
                        max_clocks: int = 2_000_000,
                        log_every: int = 100) -> list[int]:
    """Capture *num_samples* of delta-sigma audio_i (on audio_valid_i pulses).

    Returns a list of signed 14-bit integers.
    """
    audio_samples: list[int] = []

    for _ in range(max_clocks):
        await RisingEdge(dut.clk)

        if get_ds_audio_valid(dut):
            audio_val = get_ds_audio_i(dut)
            audio_samples.append(audio_val)

            if log_every and (len(audio_samples) % log_every == 0
                              or len(audio_samples) <= 3):
                dut._log.info(
                    f"[sample {len(audio_samples):4d}] "
                    f"audio_i = {audio_val:6d}"
                )
            if len(audio_samples) >= num_samples:
                break

    return audio_samples


# =============================================================================
#  Tests
# =============================================================================

WAVEFORM_NAMES = {
    WAVE_TRI:   "Triangle",
    WAVE_SAW:   "Sawtooth",
    WAVE_PULSE: "Pulse",
    WAVE_NOISE: "Noise",
}

@cocotb.test()
async def test_waveforms(dut):
    """Sweep all four waveform types at 440 Hz and plot each one,
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
        title="audio_i — All Waveforms @ 440 Hz",
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
