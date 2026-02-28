//-------------------------------------------------------------------------------------------------
//
//  File: tick_gen.sv
//  Description: Generate 50 kHz tick.
//
//  Author:
//    - Andreas Pedersen
//
//-------------------------------------------------------------------------------------------------

/*
  Instantiation Template:

  tick_gen tick_gen_inst (
    .clk_i  (),
    .rst_ni (),
    .tick_o ()
  );
*/

module tick_gen (
  input  logic clk_i,
  input  logic rst_ni,
  output logic tick_o
);
  logic [9:0] cnt;

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      cnt    <= 0;
      tick_o <= 0;
    end else begin
      if (cnt == 10'd499) begin
        cnt    <= 0;
        tick_o <= 1'b1;
      end else begin
        cnt    <= cnt + 1;
        tick_o <= 1'b0;
      end
    end
  end
endmodule