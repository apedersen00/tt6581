![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg)

# TT6581

Inspired by the legendary MOS6581 Sound Interface Device (SID) chip used in retro computers such as the Commodore 64, the _Tiny Tapeout_ 6581 (TT6581) is a completely digital interpretation supporting nearly the entire original MOS6581 feature set, implemented in 2x2 tiles for Tiny Tapeout.

As a demonstration, here are two songs that **are produced by RTL testbenches**:

1. **Port of _Monty on the Run_ by Rob Hubbard**

https://github.com/user-attachments/assets/aede3a49-307a-4b56-abea-9a842e0d1250

2. **10-second Nocturne demonstrating the filter**

https://github.com/user-attachments/assets/fff6d938-7d75-444d-9261-1e6ea31e3630

## Features

- Full control through a Serial-Peripheral Interface (SPI).
- Three independently synthesized voices.
- Four supported waveform types (triangle, sawtooth, square and noise).
- Attack, decay, sustain, release (ADSR) envelope shaping.
- Chamberlin State-Variable Filter (SVF) for low-pass, high-pass, band-pass and band-reject.
- Second-order Delta-Sigma DAC.

## Architecture

![TT6581 Architecture](media/tt6581_datapath.png)

The diagram above shows the datapath in the TT6581. A tick generator triggers the generation of a single audio sample.

1. **Voice Generation:** One 10-bit voice at a time is generated. Internal phase registers keep track of each voice's state while inactive. The frequency and waveform type are set by the programmed values in the register file.

2. **Envelope:** An envelope value from 255 (max) to 0 (min) is generated and applied to each voice one at a time by multiplication.

3. **Wave Accumulation:** The three voices are accumulated (mixed) by addition. Depending on the filter enable bit of each voice, they are accumulated in one of two registers: one that will be passed through the SVF, and one that will bypass it.

4. **Filter:** The SVF is applied to the voices with filtering enabled. It is a Chamberlin State-Variable Filter and produces a low-pass, high-pass, band-pass or band-reject output depending on configuration. Both cutoff frequency and resonance (Q) are tuneable. Running the filter on one sample requires three multiplications.

5. **Global Volume:** The SVF output is summed with the voices in the bypass accumulator. A global 8-bit volume is applied by multiplication. The result is the final mix.

6. **Delta-Sigma PDM:** An error-feedback Delta-Sigma modulator produces a 1-bit PDM output. The modulator runs at 10 MHz for an oversampling ratio (OSR) of 200.

## Pin Mapping

The TT6581 uses the bidirectional IO pins for SPI and a single dedicated output for the PDM audio signal. All dedicated inputs are unused.

| Pin        | Direction | Function                     |
| ---------- | --------- | ---------------------------- |
| `uio[0]`   | Input     | SPI Chip Select (active low) |
| `uio[1]`   | Input     | SPI MOSI                     |
| `uio[2]`   | Output    | SPI MISO                     |
| `uio[3]`   | Input     | SPI SCLK                     |
| `uio[4:7]` | -         | Unused                       |
| `uo[0]`    | Output    | PDM audio output             |
| `uo[1:7]`  | -         | Unused                       |
| `ui[0:7]`  | -         | Unused                       |

The PDM output should be passed through a 4th order Bessel filter for the best reconstruction of the analog waveform.

## Quick Start

The TT6581 is programmed in much the same way as the original MOS6581. The register layout mirrors the original SID — three voice channels followed by filter and volume registers — and the same ADSR, waveform selection and filter concepts apply. The main differences are:

- Registers are accessed through an SPI interface.
- The filter coefficients are pre-calculated and written directly as fixed-point values, rather than the raw 11-bit FC value used by the MOS6581.

### SPI Protocol

The SPI interface uses CPOL=0, CPHA=0 (data sampled on the rising edge of SCLK). Each transaction is a 16-bit frame while CS is held low:

| Bit   | 15         | 14:8            | 7:0          |
| ----- | ---------- | --------------- | ------------ |
| Field | R/W        | Address \[6:0\] | Data \[7:0\] |

- **Bit 15** = `1` for write, `0` for read.
- **Bits 14:8** = 7-bit register address.
- **Bits 7:0** = write data (writes) or don't-care (reads; MISO returns the register value).

Data is transmitted MSB first.

### Playing a tone

1. **Set volume:** Write `0xFF` to register `0x1A` (VOLUME) for full volume.
2. **Set frequency:** Compute the 16-bit frequency control word and write it to `FREQ_LO` / `FREQ_HI`.
3. **Set ADSR:** Write attack/decay to `AD` and sustain/release to `SR`.
4. **Select waveform and gate on:** Write the CONTROL register with the desired waveform bit and `GATE=1`.

For example, to play a 440 Hz sawtooth on Voice 0 with instant attack and full sustain:

```
SPI Write: addr=0x1A, data=0xFF    # Volume = max
SPI Write: addr=0x00, data=0xC5    # FREQ_LO = 0xC5  (FCW for 440 Hz = 0x0EC5)
SPI Write: addr=0x01, data=0x0E    # FREQ_HI = 0x0E
SPI Write: addr=0x05, data=0x00    # AD = 0x00 (attack=0, decay=0)
SPI Write: addr=0x06, data=0xF0    # SR = 0xF0 (sustain=15, release=0)
SPI Write: addr=0x04, data=0x21    # CONTROL = sawtooth + gate on
```

To release the note, write CONTROL again with `GATE=0`:

```
SPI Write: addr=0x04, data=0x20    # CONTROL = sawtooth + gate off
```

### Formulas

**Frequency Control Word (FCW):**

$$
FCW = \frac{f_{\text{desired}} \times 2^{19}}{F_s}
$$

where $F_s = 50$ kHz (sample rate). The 16-bit FCW is split across `FREQ_LO` (bits 7:0) and `FREQ_HI` (bits 15:8).

**Filter Cutoff Coefficient** (Q1.15 signed):

$$
\text{FCC} = \left[ 2 \cdot \sin\!\left(\frac{\pi \cdot f_c}{F_s}\right) \cdot 32768 \right]
$$

where $f_c$ is the desired cutoff frequency in Hz. The 16-bit result is split across `F_LO` and `F_HI`.

**Filter Damping Coefficient** (Q4.12 signed):

$$
\text{FDC} = \left[ \frac{1}{Q} \cdot 4096 \right]
$$

where $Q$ is the desired resonance. The 16-bit result is split across `Q_LO` and `Q_HI`.

## Register Map

The TT6581 has a 7-bit address space (128 registers). Three identical voice register groups are followed by a filter/volume group.

The full register map is described in `regs.yaml`.

### Voice Registers

Each voice occupies 7 consecutive registers. Voice 0 starts at `0x00`, Voice 1 at `0x07`, and Voice 2 at `0x0E`.

| Offset | Name    | Bits | Description                        |
| ------ | ------- | ---- | ---------------------------------- |
| 0x00   | FREQ_LO | 7:0  | Frequency control word - low byte  |
| 0x01   | FREQ_HI | 7:0  | Frequency control word - high byte |
| 0x02   | PW_LO   | 7:0  | Pulse width - low byte             |
| 0x03   | PW_HI   | 3:0  | Pulse width - high byte            |
| 0x04   | CONTROL | 7:0  | Waveform select and voice control  |
| 0x05   | AD      | 7:0  | Attack (7:4) / Decay (3:0)         |
| 0x06   | SR      | 7:0  | Sustain (7:4) / Release (3:0)      |

**CONTROL register bit fields:**

| Bit | Name     | Description                    |
| --- | -------- | ------------------------------ |
| 7   | NOISE    | Select noise waveform          |
| 6   | PULSE    | Select pulse (square) waveform |
| 5   | SAW      | Select sawtooth waveform       |
| 4   | TRI      | Select triangle waveform       |
| 3   | -        | Reserved                       |
| 2   | RING_MOD | Enable ring modulation         |
| 1   | SYNC     | Enable oscillator sync         |
| 0   | GATE     | Gate (1 = attack, 0 = release) |

### Filter and Volume Registers

| Address | Name    | Bits | Description                            |
| ------- | ------- | ---- | -------------------------------------- |
| 0x15    | F_LO    | 7:0  | Filter cutoff coefficient - low byte   |
| 0x16    | F_HI    | 7:0  | Filter cutoff coefficient - high byte  |
| 0x17    | Q_LO    | 7:0  | Filter damping coefficient - low byte  |
| 0x18    | Q_HI    | 7:0  | Filter damping coefficient - high byte |
| 0x19    | EN_MODE | 5:0  | Filter enable and mode select          |
| 0x1A    | VOLUME  | 7:0  | Global volume (0x00–0xFF)              |

**EN_MODE bit fields:**

| Bit | Name    | Description                                         |
| --- | ------- | --------------------------------------------------- |
| 5   | FILT_V2 | Route Voice 2 through filter                        |
| 4   | FILT_V1 | Route Voice 1 through filter                        |
| 3   | FILT_V0 | Route Voice 0 through filter                        |
| 2:0 | MODE    | Filter mode: `001`=LP, `010`=BP, `100`=HP, `101`=BR |

## Building and Testing

The project contains two separate testbench environments:

1. C++ testbenches for Verilator
2. CocoTB testbenches

The C++ Verilator testbenches are significantly faster and were the main tool for verification during development. The CocoTB testbenches were implemented as high-level verification that can also run on the synthesized gate-level netlist.

### Verilator

Verilator testbenches are stored in `sim/`:

```
sim
├── cpp         # C++ testbenches
├── logs        # Waveform files
├── tmp         # Temporary data files from the TBs
├── out         # Testbench results
├── scripts     # Python scripts for parsing TB intermediate files in out/
├── stimulus    # Stimulus file for tt6581_player TB
├── tb          # SystemVerilog wrappers for the testbenches
└── Makefile    # Makefile for running the testbenches
```

To run a testbench, simply run make and specify the simulation target:

```bash
make tt6581
make tt6581_player
make tt6581_bode
make svf
make spi
make mult
make envelope
make delta_sigma
```

A brief description of each testbench:

- **tt6581:** Produces a 10-second song (`.wav` file). Intended to demonstrate most of the TT6581's capabilities. Uses all three voices and the filter.

- **tt6581_player:** This testbench simulates and plays the entirety of _Monty on the Run_ by Rob Hubbard by reading the stimulus file `stimulus/Hubbard_Rob_Monty_on_the_Run_tt6581_stimulus.txt`. The stimulus was generated by running the assembly code for _Monty on the Run_ (from [this](https://github.com/realdmx/c64_6581_sid_players) repository) in a modified 6502 emulator that records all memory writes to the SID. The recorded memory writes were then translated to work on the TT6581.

- **tt6581_bode**: Simply plays a sine sweep and records the output. Produces a bode plot. Intended to check the frequency range.

- **svf:** Tests the Chamberlin SVF in all four supported modes. A sine sweep is used as the input. Produces four frequency response plots as the output.

- **mult:** Tests the 24x16 shift-add multiplier. Inputs N randomly generated operands and verifies the hardware result against software.

- **envelope:** Tests the envelope generator by inputting known ADSR values with a constant wave input. Plots the produced envelope.

### CocoTB

Currently has three testbenches. They are automatically run as a GitHub Action on push. When all three tests have completed, a summary is generated and stored. More importantly, these tests are also run on the synthesized gate-level netlist. To see the three tests and the summary, simply go to a successful `test` or `gl_test` run.

- [Latest test results](https://github.com/apedersen00/tt6581/actions/workflows/test.yaml?query=is%3Asuccess)
- [Latest gate-level test results](https://github.com/apedersen00/tt6581/actions/workflows/gds.yaml?query=is%3Asuccess)
