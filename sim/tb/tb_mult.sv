//-------------------------------------------------------------------------------------------------
//
//  File: tb_mult.sv
//  Description: Wrapper for Verilator testbench.
//
//  Author:
//      - Andreas Pedersen
//
//-------------------------------------------------------------------------------------------------

module tb_mult
  (
    input   logic                clk_i,
    input   logic signed [23:0]  op_a_i,
    input   logic signed [15:0]  op_b_i,
    input   logic                rst_ni,
    input   logic                start_i,
    output  logic                ready_o,
    output  logic signed [39:0]  prod_o
  );

    // DUT instance
    mult mult_inst (
      .*
    );

    // Stimulus
    initial begin
      if ($test$plusargs("trace") != 0) begin
        $dumpfile("logs/tb_mult.vcd");
        $dumpvars();
      end

      $display("[%0t] Starting simulation...", $time);
    end

endmodule
