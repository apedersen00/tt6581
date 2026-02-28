//-------------------------------------------------------------------------------------------------
//
//  File: tb_svf.sv
//  Description: Wrapper for Verilator testbench.
//
//  Author:
//      - Andreas Pedersen
//
//-------------------------------------------------------------------------------------------------

module tb_svf (
  input  logic        clk_i,
  input  logic        rst_ni,
  input  logic        start_i,

  input  logic [2:0]  filt_sel_i,
  input  logic [13:0] wave_i,
  
  input  logic signed [15:0] coeff_f_i, 
  input  logic signed [15:0] coeff_q_i, 

  output logic        ready_o,
  output logic [13:0] wave_o
);

  logic mult_ready;
  logic mult_start;

  logic [23:0] mult_a;
  logic [15:0] mult_b;
  logic [39:0] mult_prod;

  // DUT instance
  svf svf_inst (
    .clk_i        ( clk_i       ),
    .rst_ni       ( rst_ni      ),
    .start_i      ( start_i     ),
    .filt_sel_i   ( filt_sel_i  ),
    .wave_i       ( wave_i      ),
    .coeff_f_i    ( coeff_f_i   ),
    .coeff_q_i    ( coeff_q_i   ),
    .mult_ready_i ( mult_ready  ),
    .mult_prod_i  ( mult_prod   ),
    .mult_a_o     ( mult_a      ),
    .mult_b_o     ( mult_b      ),
    .mult_start_o ( mult_start  ),
    .ready_o      ( ready_o     ),
    .wave_o       ( wave_o      )
  );

  mult mult_inst (
    .clk_i        ( clk_i       ),
    .rst_ni       ( rst_ni      ),
    .start_i      ( mult_start  ),
    .op_a_i       ( mult_a      ),
    .op_b_i       ( mult_b      ),
    .ready_o      ( mult_ready  ),
    .prod_o       ( mult_prod   )
  );

  // Stimulus
  initial begin
    if ($test$plusargs("trace") != 0) begin
      $dumpfile("logs/tb_svf.vcd");
      $dumpvars();
    end

    $display("[%0t] Starting simulation...", $time);
  end

endmodule
