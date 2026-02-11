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
    .op_a_i   (),
    .op_b_i   (),
    .rst_ni   (),
    .start_i  (),
    .ready_o  (),
    .prod_o   ()
  );
*/


module mult (
    input   logic       clk_i,
    input   logic       rst_ni,
    input   logic       start_i,
    input   logic [9:0] op_a_i,   // Operand A (10 bit)
    input   logic [7:0] op_b_i,   // Operand B (8 bit)
    output  logic       ready_o,
    output  logic [9:0] prod_o    // Product
);

  /************************************
   * Signals and assignments
   ***********************************/
  logic [3:0]   iter;
  logic [17:0]  accum;
  logic         busy;
  logic [17:0]  a_reg;
  logic [7:0]   b_reg;

  assign ready_o = (iter == 8);
  assign prod_o  = accum[17:8];

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
      STATE_READY: nxt_state = start_i      ? STATE_ITER  : STATE_READY;
      STATE_ITER:  nxt_state = (iter == 8)  ? STATE_READY : STATE_ITER;
    endcase
  end

  /************************************
   * Sequential multiplication
   ***********************************/
  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      iter  <= '0;
      accum <= '0;
      a_reg <= '0;
      b_reg <= '0;
    end else begin
      unique case (cur_state)
        STATE_READY: begin
          if (start_i) begin
            a_reg <= {8'd0, op_a_i};
            b_reg <= op_b_i;
            accum <= '0;
            iter  <= '0;
          end
        end

        STATE_ITER: begin
          if (iter != 8) begin
            if (b_reg[0]) begin
              accum <= accum + a_reg;
            end
            a_reg <= {a_reg[16:0], 1'b0};
            b_reg <= {1'b0, b_reg[7:1]};
            iter  <= iter + 1;
          end
        end
      endcase
    end
  end

endmodule
