![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg)

# TT6581

Inspired by the legendary MOS6581 Sound Interface Device (SID) chip used in retro computers such as the Commodore 64, the _Tiny Tapeout_ 6581 (TT6581) is a completely digital interpretation supporting nearly the entire original MOS6581 feature set implemeted in 2x2 tiles for Tiny Tapeout.



## Features

- Full control through a Serial-Peripheral Interface (SPI).
- Three independently synthesized voices.
- Four supported waveform types (triangle, sawtooth, square and noise).
- Attack, decay, sustain, release (ADSR) envelope shaping.
- Chamberlin State-Variable Filter (SVF) for low-pass, high-pass, band-pass and band-reject.
- Second-order Delta-Sigma DAC.

## Architecture

![TT6581 Architecture](media/tt6581_datapath.png)

Above the rough diagram shows the datapath in the TT6581. A tick generator enables the generation of a single audio sample.

1. *Voice Generation:* One 10-bit voice at a time is generated. Internal phase registers keep track of each voice's state while inactive. The frequency and waveform type is set by the programmed values in the register file.

2. *Envelope:* An envelope value from 255 (max) to 0 (min) is generated and applied to each voice one at a time by multiplication.

3. *Wave Accumulation:* The three voices are accumulated (mixed) by addition. Depending on the filter enable bit of each voice, they are accumulated in one of two registers: one that will be passed through the SVF, and one that will bypass it.

4. *Filter:*  The SVF is applied to the voices with filtering enabled. The filter is a Chamberlin State-Variable Filter and produce a low-pass, high-pass, band-pass or band-reject filter depending on configuration. Both cut-off frequency and resonance (Q) are tuneable. Running the filter on one sample requires three multiplications.

5. *Global Volume:* The SVF output is summed with the voices in the bypass accumulator. A global 8-bit volume is applied by multiplication. The result is the final mix.

6. *Delta-Sigma PDM:* A Error-Feedback Delta-Sigma modulator produces a 1-bit PDM output. The modulator runs at 10 MHz for an Oversampling-Rate (OSR) of 200.

## Pin Mapping

## Quick Start

## Register Map

## Building and Testing

The project contains two separate testbench environments:

1. C++ testbenches for Verilator
2. CocoTB testbenches

The C++ Verilator testbenches are significantly faster and was the main tool for verification during development. 