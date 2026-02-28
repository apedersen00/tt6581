//-------------------------------------------------------------------------------------------------
//
//  File: delta_sigma.sv
//  Description: Delta-Sigma digital to analog converter.
//
//  Author:
//    - Andreas Pedersen
//
//-------------------------------------------------------------------------------------------------

/*
  Instantiation Template:

  delta_sigma delta_sigma_inst (
    .clk_i          (),
    .rst_ni         (),
    .audio_valid_i  (),
    .audio_i        (),
    .wave_o         ()
  );
*/


module delta_sigma (
    input   logic               clk_i,        // 50 MHz
    input   logic               rst_ni,
    input   logic               audio_valid_i,
    input   logic signed [13:0] audio_i,
    output                      wave_o
);

  /************************************
   * Counter for CLK division (1/5)
   ***********************************/
  logic [2:0] cnt;
  logic       en;

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      cnt <= '0;
      en  <= '0;
    end else begin
      if (cnt == 3'd4) begin
        cnt <= 3'd0;
        en  <= 1'b1;
      end else begin
        cnt <= cnt + 3'd1;
        en  <= 1'b0;
      end
    end
  end

  /************************************
   * Sample/Hold
   ***********************************/
  logic signed [18:0] audio;

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni)            audio <= '0;
    else if (audio_valid_i) audio <= {audio_i[13], audio_i, 4'b0};
  end

  /************************************
   * Error Feedback Modulator
   ***********************************/
  logic signed [18:0] e1;
  logic signed [18:0] e2;
  logic signed [18:0] y;
  logic               ds;

  assign y = audio + (e1 <<< 1) - e2;

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      e1 <= '0;
      e2 <= '0;
      ds <= '0;
    end else if (en) begin
      if (y >= 0) begin
        ds <= 1'b1;
        e1 <= y - 19'sd32768;
      end else begin
        ds <= 1'b0;
        e1 <= y + 19'sd32768;
      end
      e2 <= e1;
    end
  end

  assign wave_o = ds;

endmodule
