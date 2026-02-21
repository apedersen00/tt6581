//---------------------------------------------------------
//
//  File: mult.sv
//  Description: Shift-add multiplier.
//
//---------------------------------------------------------

/*
  Instantiation Template:

  mult mult_inst (
    .clk_i    (),
    .rst_ni   (),
    .start_i  (),
    .op_a_i   (),
    .op_b_i   (),
    .ready_o  (),
    .prod_o   ()
  );
*/


module mult (
    input   logic               clk_i,
    input   logic               rst_ni,
    input   logic               start_i,
    input   logic signed [23:0] op_a_i,   // Operand A (24 bit)
    input   logic signed [15:0] op_b_i,   // Operand B (16 bit)
    output  logic               ready_o,
    output  logic signed [39:0] prod_o    // Product
);

  /************************************
   * Signals and assignments
   ***********************************/
  logic [39:0] accum;
  logic [39:0] a_reg;
  logic [15:0] b_reg;

  logic [4:0] iter;
  logic       neg_result;

  assign ready_o = (iter == 5'd16) && !start_i;
  assign prod_o  = neg_result ? (~accum + 40'd1) : accum;

  /************************************
   * State machine
   ***********************************/
  typedef enum logic {
    STATE_READY,
    STATE_ITER
  } state_e;

  state_e cur_state, nxt_state;

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni)  cur_state <= STATE_READY;
    else          cur_state <= nxt_state;
  end

  always_comb begin
    nxt_state = STATE_READY;
    case (cur_state)
      STATE_READY: begin
        if (start_i) nxt_state = STATE_ITER;
        else         nxt_state = STATE_READY;
      end
      STATE_ITER: begin
        if (iter == 5'd16) nxt_state = STATE_READY;
        else               nxt_state = STATE_ITER;
      end
    endcase
  end

  /************************************
   * Sequential multiplication
   ***********************************/
  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      iter       <= '0;
      accum      <= '0;
      a_reg      <= '0;
      b_reg      <= '0;
      neg_result <= '0;
    end else begin
      unique case (cur_state)
        STATE_READY: begin
          if (start_i) begin
            neg_result <= op_a_i[23] ^ op_b_i[15];
            a_reg      <= {16'd0, op_a_i[23] ? -op_a_i : op_a_i};
            b_reg      <= op_b_i[15] ? -op_b_i : op_b_i;
            accum      <= '0;
            iter       <= '0;
          end
        end

        STATE_ITER: begin
          if (iter != 5'd16) begin
            if (b_reg[0]) begin
              accum <= accum + a_reg;
            end
            a_reg <= {a_reg[38:0], 1'b0};
            b_reg <= {1'b0, b_reg[15:1]};
            iter  <= iter + 1;
          end
        end
      endcase
    end
  end

endmodule
