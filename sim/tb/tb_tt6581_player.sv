//-------------------------------------------------------------------------------------------------
//
//  File: tb_tt6581_player.sv
//
//  Description: Wrapper for Verilator testbench.
//
//  Author:
//      - A. Pedersen
//
//-------------------------------------------------------------------------------------------------

module tb_tt6581_player (
  input   logic       clk_i,      // System clock (50 MHz)
  input   logic       rst_ni,     // Active low reset
  input   logic       sclk_i,     // SPI Clock
  input   logic       cs_i,       // SPI Chip select
  input   logic       mosi_i,     // SPI MOSI
  output  logic       miso_o,     // SPI MISO
  output  logic       wave_o
);

    // DUT instance
  tt6581 tt6581_inst (
    .clk_i  ( clk_i   ),
    .rst_ni ( rst_ni  ),
    .sclk_i ( sclk_i  ),
    .cs_i   ( cs_i    ),
    .mosi_i ( mosi_i  ),
    .miso_o ( miso_o  ),
    .wave_o ( wave_o  )
  );

    // Stimulus & waveform dump
    initial begin
      if ($test$plusargs("trace") != 0) begin
        $dumpfile("logs/tb_tt6581_player.vcd");
        $dumpvars();
      end

      $display("[%0t] SID Player Testbench — Starting simulation...", $time);
    end

endmodule
