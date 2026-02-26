//-------------------------------------------------------------------------------------------------
//
//  File: tb_delta_sigma.sv
//
//  Author:
//      - A. Pedersen
//
//-------------------------------------------------------------------------------------------------

module tb_delta_sigma
(
  input   logic               clk_i,        // 50 MHz
  input   logic               rst_ni,
  input   logic               audio_valid_i,
  input   logic signed [13:0] audio_i,
  output                      wave_o
);

  // DUT instance
  delta_sigma delta_sigma_inst (
    .*
  );

  // Stimulus
  initial begin
    if ($test$plusargs("trace") != 0) begin
      $dumpfile("logs/tb_delta_sigma.vcd");
      $dumpvars();
    end

    $display("[%0t] Starting simulation...", $time);
  end

endmodule
