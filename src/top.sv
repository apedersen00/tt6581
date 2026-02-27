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

  // SPI
  logic sclk;
  logic cs;
  logic mosi;
  logic miso;

  // Delta-Sigma PDM output
  logic pdm;

  // SPI pin mapping
  assign cs         = uio_in[0];
  assign mosi       = uio_in[1];
  assign uio_out[2] = miso;
  assign sclk       = uio_in[3];

  // Tie off unused bidirectional outputs
  assign uio_out[1:0] = 2'b0;
  assign uio_out[7:3] = 5'b0;

  // Bidirectional IO enables
  assign uio_oe = 8'b00000100;

  // Dedicated outputs
  assign uo_out[0]   = pdm;
  assign uo_out[7:1] = 7'b0;

  tt6581 tt6581_inst (
    .clk_i  ( clk       ),
    .rst_ni ( rst_n     ),
    .sclk_i ( sclk      ),
    .cs_i   ( cs        ),
    .mosi_i ( mosi      ),
    .miso_o ( miso      ),
    .wave_o ( pdm       )
  );

  wire _unused_ok = &{
      ena,
      uio_in[7:4],
      ui_in,
      1'b0
  };

endmodule