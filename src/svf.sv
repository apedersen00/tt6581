//-------------------------------------------------------------------------------------------------
//
//  File: svf.sv
//  Description: Chamberlin State-Variable Filter (SVF).
//
//  Author:
//    - Andreas Pedersen
//
//-------------------------------------------------------------------------------------------------

/*
  Instantiation Template:

  svf svf_inst (
    .clk_i        (),
    .rst_ni       (),
    .start_i      (),
    .filt_sel_i   (),
    .wave_i       (),
    .coeff_f_i    (),
    .coeff_q_i    (),
    .mult_ready_i (),
    .mult_prod_i  (),
    .mult_a_o     (),
    .mult_b_o     (),
    .mult_start_o (),
    .ready_o      (),
    .wave_o       ()
  );
*/

module svf (
  input   logic               clk_i,
  input   logic               rst_ni,
  input   logic               start_i,
  input   logic [2:0]         filt_sel_i,   // Filter select
  input   logic signed [13:0] wave_i,       // Unsigned voice mix
  input   logic signed [15:0] coeff_f_i,    // Q1.15 frequency coeff
  input   logic signed [15:0] coeff_q_i,    // Q4.12 damping coeff

  // Multiplier
  input   logic               mult_ready_i,
  input   logic signed [39:0] mult_prod_i,
  output  logic signed [23:0] mult_a_o,
  output  logic signed [15:0] mult_b_o,
  output  logic               mult_start_o,

  output  logic               ready_o,
  output  logic signed [13:0] wave_o        // Unsigned filtered output
);

  /************************************
   * State machine
   ***********************************/
  typedef enum logic [3:0] {
    STATE_IDLE,
    STATE_MULT_Q,
    STATE_WAIT_Q,
    STATE_CALC_HP,
    STATE_MULT_F1,
    STATE_WAIT_F1,
    STATE_CALC_BP,
    STATE_MULT_F2,
    STATE_WAIT_F2,
    STATE_CALC_LP,
    STATE_DONE
  } state_e;

  state_e cur_state, nxt_state;

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni)  cur_state <= STATE_IDLE;
    else          cur_state <= nxt_state;
  end

  always_comb begin
    nxt_state = cur_state;
    unique case (cur_state)
      STATE_IDLE:     if (start_i)      nxt_state = STATE_MULT_Q;
      STATE_MULT_Q:                     nxt_state = STATE_WAIT_Q;
      STATE_WAIT_Q:   if (mult_ready_i) nxt_state = STATE_CALC_HP;
      STATE_CALC_HP:                    nxt_state = STATE_MULT_F1;
      STATE_MULT_F1:                    nxt_state = STATE_WAIT_F1;
      STATE_WAIT_F1:  if (mult_ready_i) nxt_state = STATE_CALC_BP;
      STATE_CALC_BP:                    nxt_state = STATE_MULT_F2;
      STATE_MULT_F2:                    nxt_state = STATE_WAIT_F2;
      STATE_WAIT_F2:  if (mult_ready_i) nxt_state = STATE_CALC_LP;
      STATE_CALC_LP:                    nxt_state = STATE_DONE;
      STATE_DONE:                       nxt_state = STATE_IDLE;
      default: ;
    endcase
  end

  /************************************
   * Signals
   ***********************************/
  logic signed [23:0] reg_band;
  logic signed [23:0] reg_low;
  logic signed [23:0] hp_node;
  logic signed [23:0] bp_node;
  logic signed [23:0] lp_node;

  assign ready_o = (cur_state == STATE_DONE);

  logic signed [23:0] mult_q_shifted;
  logic signed [23:0] mult_f_shifted;
  assign mult_q_shifted = mult_prod_i[35:12];
  assign mult_f_shifted = mult_prod_i[38:15];

  /************************************
   * Multiplication
   ***********************************/
  always_comb begin
    mult_a_o     = '0;
    mult_b_o     = '0;
    mult_start_o = 1'b0;

    unique case (cur_state)
      STATE_MULT_Q: begin
        mult_a_o     = reg_band;
        mult_b_o     = coeff_q_i;
        mult_start_o = 1'b1;
      end
      STATE_MULT_F1: begin
        mult_a_o     = hp_node;
        mult_b_o     = coeff_f_i;
        mult_start_o = 1'b1;
      end
      STATE_MULT_F2: begin
        mult_a_o     = bp_node;
        mult_b_o     = coeff_f_i;
        mult_start_o = 1'b1;
      end
      default: ;
    endcase
  end

  /************************************
   * Filter computation
   ***********************************/
  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      reg_band <= '0;
      reg_low  <= '0;
      hp_node  <= '0;
      bp_node  <= '0;
      lp_node  <= '0;
    end else begin
      unique case (cur_state)
        STATE_CALC_HP:
          hp_node <= { {10{wave_i[13]}}, wave_i } - reg_low - mult_q_shifted;

        STATE_CALC_BP: begin
          bp_node  <= reg_band + mult_f_shifted;
          reg_band <= reg_band + mult_f_shifted;
        end

        STATE_CALC_LP: begin
          lp_node <= reg_low + mult_f_shifted;
          reg_low <= reg_low + mult_f_shifted;
        end

        default: ;
      endcase
    end
  end

  /************************************
   * Output mux
   ***********************************/
  logic signed [23:0] br_node;
  assign br_node = hp_node + lp_node;

  logic signed [23:0] selected_out;
  always_comb begin
    case (filt_sel_i)
      3'b001:  selected_out = lp_node;
      3'b010:  selected_out = bp_node;
      3'b100:  selected_out = hp_node;
      3'b101:  selected_out = br_node;
      default: selected_out = lp_node;
    endcase
  end

  always_comb begin
    if (selected_out > 24'sd8191)       wave_o = 14'sd8191;
    else if (selected_out < -24'sd8192) wave_o = -14'sd8192;
    else                                wave_o = selected_out[13:0];
  end

  wire _unused_ok = &{
    mult_prod_i[39],
    mult_prod_i[11:0]
  };

endmodule