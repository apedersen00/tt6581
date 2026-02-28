//-------------------------------------------------------------------------------------------------
//
//  File: tb_envelope.sv
//  Description: Wrapper for Verilator testbench.
//
//  Author:
//      - Andreas Pedersen
//
//-------------------------------------------------------------------------------------------------

module tb_envelope (
  input   logic         clk_i,
  input   logic         rst_ni,
  input   logic         start_i,      // Start processing voice_idx_i

  input   logic [9:0]   voice_i,

  input   logic [1:0]   voice_idx_i,  // Active voice [0-2]
  input   logic         gate_i,       // Gate control

  input   logic [3:0]   attack_i,
  input   logic [3:0]   decay_i,
  input   logic [3:0]   sustain_i,
  input   logic [3:0]   release_i,

  output  logic         ready_o,
  output  logic [39:0]  prod_o
);

  logic         mult_ready;
  logic         mult_start;
  logic [23:0]  op_a;
  logic [15:0]  op_b;
  logic [7:0]   env_raw;

  assign op_a = {{14{voice_i[9]}}, voice_i};
  assign op_b = {8'd0, env_raw};

  // DUT instance
  envelope envelope_inst (
    .clk_i        ( clk_i       ),
    .rst_ni       ( rst_ni      ),
    .start_i      ( start_i     ),
    .voice_idx_i  ( voice_idx_i ),
    .gate_i       ( gate_i      ),
    .attack_i     ( attack_i    ),
    .decay_i      ( decay_i     ),
    .sustain_i    ( sustain_i   ),
    .release_i    ( release_i   ),
    .mult_ready_i ( mult_ready  ),
    .mult_start_o ( mult_start  ),
    .env_raw_o    ( env_raw     ),
    .ready_o      ( ready_o     )
  );

  mult mult_inst (
    .clk_i        ( clk_i       ),
    .rst_ni       ( rst_ni      ),
    .start_i      ( mult_start  ),
    .op_a_i       ( op_a        ),
    .op_b_i       ( op_b        ),
    .ready_o      ( mult_ready  ),
    .prod_o       ( prod_o      )
  );

  // Stimulus
  initial begin
    if ($test$plusargs("trace") != 0) begin
      $dumpfile("logs/tb_envelope.vcd");
      $dumpvars();
    end

    $display("[%0t] Starting simulation...", $time);
  end

endmodule
