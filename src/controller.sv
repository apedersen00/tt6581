//-------------------------------------------------------------------------------------------------
//
//  File: controller.sv
//  Description: Master controller for TT6581.
//
//  Author:
//    - Andreas Pedersen
//
//-------------------------------------------------------------------------------------------------

/*
  Instantiation Template:

  controller controller_inst (
    .clk_i          (),
    .rst_ni         (),
    .sample_tick_i  (),

    // Register file
    .freq_lo_i      (),
    .freq_hi_i      (),
    .pw_lo_i        (),
    .pw_hi_i        (),
    .control_i      (),
    .ad_i           (),
    .sr_i           (),

    // Voice generator
    .voice_ready_i  (),
    .voice_wave_i   (),
    .voice_start_o  (),
    .voice_idx_o    (),
    .voice_freq_o   (),
    .voice_pw_o     (),
    .voice_wave_o   (),

    .audio_valid_o  (),
    .audio_o        ()
  );
*/

module controller (
  input   logic               clk_i,          // 50 MHz
  input   logic               rst_ni,         // Active low reset
  input   logic               sample_tick_i,  // 50 kHz tick

  // Register file
  input logic [2:0][7:0]     freq_lo_i,
  input logic [2:0][7:0]     freq_hi_i,
  input logic [2:0][7:0]     pw_lo_i,
  input logic [2:0][7:0]     pw_hi_i,
  input logic [2:0][7:0]     control_i,
  input logic [2:0][7:0]     ad_i,
  input logic [2:0][7:0]     sr_i,

  // Voice generator
  input   logic               voice_ready_i,  // Voice ready
  input   logic [9:0]         voice_wave_i,   // Raw generated voice
  output  logic               voice_start_o,  // Start voice gen
  output  logic [3:0]         voice_idx_o,    // Active voice index
  output  logic [15:0]        voice_freq_o,   // Active voice freq
  output  logic [11:0]        voice_pw_o,     // Active voice pulse width
  output  logic [3:0]         voice_wave_o,   // Active voice select

  output  logic               audio_valid_o,
  output  logic [15:0]        audio_o
);

  /************************************
   * Signals and assignments
   ***********************************/
  logic [3:0] cur_voice;
  logic signed [19:0] mix_accum;

  assign voice_idx_o  = cur_voice;
  assign voice_freq_o = {freq_hi_i[cur_voice], freq_lo_i[cur_voice]};
  assign voice_pw_o   = {pw_hi_i[cur_voice][3:0], pw_lo_i[cur_voice]};
  assign voice_wave_o = control_i[cur_voice][7:4];

  /************************************
   * State machine
   ***********************************/
  typedef enum logic [1:0] {
    STATE_IDLE,       // Wait for sample tick
    STATE_GENERATE,   // Generate voice
    STATE_ACCUMULATE, // Add to mix
    STATE_DONE
  } state_e;

  state_e cur_state, nxt_state;

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni)  cur_state <= STATE_IDLE;
    else          cur_state <= nxt_state;
  end

  always_comb begin
    nxt_state = STATE_IDLE;
    unique case (cur_state)
      STATE_IDLE:       nxt_state = sample_tick_i ? STATE_GENERATE : STATE_IDLE;
      STATE_GENERATE:   nxt_state = STATE_ACCUMULATE;
      STATE_ACCUMULATE: begin
        if      (voice_ready_i && cur_voice == 15) nxt_state = STATE_DONE;
        else if (voice_ready_i)                    nxt_state = STATE_GENERATE;
        else                                       nxt_state = STATE_ACCUMULATE;
      end
      STATE_DONE:       nxt_state = STATE_IDLE;
      default     : ;
    endcase
  end

  /************************************
   * Voice iteration
   ***********************************/
  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      cur_voice     <= '0;
      mix_accum     <= '0;
      audio_o       <= '0;
      audio_valid_o <= '0;
    end else begin
      audio_valid_o <= 1'b0;

      unique case (cur_state)

        STATE_IDLE: begin
          if (sample_tick_i) begin
            mix_accum <= '0;
            cur_voice <= '0;
          end
        end

        STATE_GENERATE: begin
          voice_start_o <= 1'b1;
        end

        STATE_ACCUMULATE: begin
          voice_start_o <= 1'b0;
          if (voice_ready_i) begin
            mix_accum <= mix_accum + {10'd0, voice_wave_i >> 2};
            cur_voice <= cur_voice + 1;
          end
        end

        STATE_DONE: begin
          audio_o       <= mix_accum[15:0];
          audio_valid_o <= 1'b1;
        end

      endcase

    end
  end


endmodule