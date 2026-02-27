//-------------------------------------------------------------------------------------------------
//
//  File: tb_spi.sv
//  Description: Wrapper for Verilator testbench.
//
//  Author:
//      - Andreas Pedersen
//
//-------------------------------------------------------------------------------------------------

module tb_spi (
  input   logic       clk_i,      // System clock (50 MHz)
  input   logic       rst_ni,     // Active low reset

  input   logic       sclk_i,     // SPI Clock
  input   logic       cs_i,       // SPI Chip select
  input   logic       mosi_i,     // SPI MOSI
  output  logic       miso_o,     // SPI MISO

  input   logic [7:0] reg_rdata_i,
  output  logic [7:0] reg_wdata_o,
  output  logic [6:0] reg_addr_o,
  output  logic       reg_we_o
);

    // DUT instance
  spi spi_inst (
    .*
  );

    // Stimulus
    initial begin
      if ($test$plusargs("trace") != 0) begin
        $dumpfile("logs/tb_spi.vcd");
        $dumpvars();
      end

      $display("[%0t] Starting simulation...", $time);
    end

endmodule
