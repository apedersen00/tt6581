/*
 * File: tt_um_andreasp00.sv
 * Description: Tiny Tapeout Top Module for SID-like Synth
 */

`default_nettype none

module tt_um_andreasp00 (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // IOs: Input path
    output wire [7:0] uio_out,  // IOs: Output path
    output wire [7:0] uio_oe,   // IOs: Enable path (active high: 0=input, 1=output)
    input  wire       ena,      // will go high when the design is enabled
    input  wire       clk,      // clock
    input  wire       rst_n     // reset_n - low to reset
);

  wire sclk = ui_in[0];
  wire cs   = ui_in[1];
  wire mosi = ui_in[2];
  logic [9:0] audio_out;

  wire miso;

  // Dedicated Outputs
  assign uo_out[0]   = miso;
  assign uo_out[7:1] = audio_out[9:3]; // Top 7 bits of audio to dedicated outputs

  // Bidirectional IO Outputs
  assign uio_out[2:0] = audio_out[2:0]; // Bottom 3 bits of audio to uio pins 0, 1, and 2
  assign uio_out[7:3] = 5'b0;           // Tie off the remaining uio output paths to 0

  // Bidirectional IO Enables
  assign uio_oe[2:0]  = 3'b111;         // Set uio[2:0] as OUTPUTS
  assign uio_oe[7:3]  = 5'b00000;       // Set uio[7:3] as INPUTS (high-Z)

  tt6581 tt6581_inst (
    .clk_i  ( clk       ),
    .rst_ni ( rst_n     ),
    .sclk_i ( sclk      ),
    .cs_i   ( cs        ),
    .mosi_i ( mosi      ),
    .miso_o ( miso      ),
    .wave_o ( audio_out )
  );

  wire _unused_ok = &{
      ena,
      uio_in,
      ui_in[7:3],
      1'b0
  };

endmodule