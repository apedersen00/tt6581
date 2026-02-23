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
    .fc_lo_i        (),
    .fc_hi_i        (),

    // Voice generator
    .voice_ready_i  (),
    .voice_start_o  (),
    .voice_idx_o    (),
    .voice_freq_o   (),
    .voice_pw_o     (),
    .voice_wave_o   (),

    // Envelope generator
    .env_ready_i    (),
    .env_start_o    (),
    .env_gate_o     (),
    .env_attack_o   (),
    .env_decay_o    (),
    .env_sustain_o  (),
    .env_release_o  (),

    .audio_valid_o  ()
  );
*/

module controller (
  input   logic               clk_i,          // 50 MHz
  input   logic               rst_ni,         // Active low reset
  input   logic               sample_tick_i,  // 50 kHz tick

  // Register file
  input logic [23:0]            freq_lo_i,
  input logic [23:0]            freq_hi_i,
  input logic [23:0]            pw_lo_i,
  input logic [23:0]            pw_hi_i,
  input logic [23:0]            control_i,
  input logic [23:0]            ad_i,
  input logic [23:0]            sr_i,

  // Voice generator
  input   logic               voice_ready_i,  // Voice ready
  output  logic               voice_start_o,  // Start voice gen
  output  logic [1:0]         voice_idx_o,    // Active voice index
  output  logic [15:0]        voice_freq_o,   // Active voice freq
  output  logic [11:0]        voice_pw_o,     // Active voice pulse width
  output  logic [3:0]         voice_wave_o,   // Active voice select
  output  logic               voice_sync_o,   // Active voice sync
  output  logic               voice_ring_mod_o, // Active voice ring modulation

  // Envelope generator
  input   logic               env_ready_i,
  output  logic               env_start_o,
  output  logic               env_gate_o,
  output  logic [3:0]         env_attack_o,
  output  logic [3:0]         env_decay_o,
  output  logic [3:0]         env_sustain_o,
  output  logic [3:0]         env_release_o,

  // Multiplier
  input   logic               mult_ready_i,
  output  logic               mult_start_o,
  output  logic [1:0]         mult_in_mux_o,    // 0: env, 1: svf, 2: vol

  // Filter
  input   logic               filt_ready_i,
  input   logic [2:0]         filt_en_i,
  output  logic               filt_start_o,

  // Output
  output  logic               accum_en_o,       // Accumulate enable
  output  logic               accum_rst_o,      // Reset accumulators
  output  logic               accum_mux_o,      // 1'b0: nofilter, 1'b1: filter

  output  logic               audio_valid_o
);

  /************************************
   * Signals and assignments
   ***********************************/
  logic [1:0] cur_voice;

  assign voice_idx_o      = cur_voice;
  assign voice_freq_o     = {freq_hi_i[cur_voice*8 +: 8], freq_lo_i[cur_voice*8 +: 8]};
  assign voice_pw_o       = {pw_hi_i[cur_voice*8 +: 4], pw_lo_i[cur_voice*8 +: 8]};
  assign voice_wave_o     = control_i[cur_voice*8+4 +: 4];
  assign voice_ring_mod_o = control_i[cur_voice*8+2];
  assign voice_sync_o     = control_i[cur_voice*8+1];

  assign env_gate_o     = control_i[cur_voice*8];
  assign env_attack_o   = ad_i[cur_voice*8+4 +: 4];
  assign env_decay_o    = ad_i[cur_voice*8 +: 4];
  assign env_sustain_o  = sr_i[cur_voice*8+4 +: 4];
  assign env_release_o  = sr_i[cur_voice*8 +: 4];


  /************************************
   * State machine
   ***********************************/
  typedef enum logic [3:0] {
    STATE_IDLE,       // Wait for sample tick
    STATE_SYN,        // Start voice waveform synthesis
    STATE_SYN_WAIT,   // Wait until voice is ready
    STATE_ENV,        // Start envelope + multiply (voice * env)
    STATE_ENV_WAIT,   // Wait until multiplication is done
    STATE_ACCUM,      // Accumulate envelope product into accumulator
    STATE_FILT,       // Start SVF
    STATE_FILT_WAIT,  // Wait until SVF is done
    STATE_VOL,        // Start volume multiply (accum * volume)
    STATE_VOL_WAIT,   // Wait for volume multiply to finish
    STATE_DONE        // Signal audio valid
  } state_e;

  state_e cur_state, nxt_state;

  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni)  cur_state <= STATE_IDLE;
    else          cur_state <= nxt_state;
  end

  always @(*) begin
    nxt_state = cur_state;
    unique case (cur_state)
      STATE_IDLE:       if (sample_tick_i)      nxt_state = STATE_SYN;
      STATE_SYN:                                nxt_state = STATE_SYN_WAIT;
      STATE_SYN_WAIT:   if (voice_ready_i)      nxt_state = STATE_ENV;
      STATE_ENV:                                nxt_state = STATE_ENV_WAIT;
      STATE_ENV_WAIT:   if (env_ready_i)        nxt_state = STATE_ACCUM;
      STATE_ACCUM:      if (cur_voice == 2'd2)  nxt_state = STATE_FILT;
                        else                    nxt_state = STATE_SYN;
      STATE_FILT:                               nxt_state = STATE_FILT_WAIT;
      STATE_FILT_WAIT:  if (filt_ready_i)       nxt_state = STATE_VOL;
      STATE_VOL:                                nxt_state = STATE_VOL_WAIT;
      STATE_VOL_WAIT:   if (mult_ready_i)       nxt_state = STATE_DONE;
      STATE_DONE:                               nxt_state = STATE_IDLE;
      default: ;
    endcase
  end

  /************************************
   * Voice counter
   ***********************************/
  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      cur_voice <= '0;
    end else begin
      if (cur_state == STATE_IDLE && sample_tick_i) cur_voice <= '0;
      else if (cur_state == STATE_ACCUM)            cur_voice <= cur_voice + 1;
    end
  end

  /************************************
   * Output signals
   ***********************************/
  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      voice_start_o   <= '0;
      env_start_o     <= '0;
      mult_start_o    <= '0;
      mult_in_mux_o   <= '0;
      accum_en_o      <= '0;
      accum_rst_o     <= '0;
      audio_valid_o   <= '0;
      filt_start_o    <= '0;
      accum_mux_o     <= '0;
    end else begin
      voice_start_o   <= '0;
      env_start_o     <= '0;
      mult_start_o    <= '0;
      mult_in_mux_o   <= '0;
      accum_en_o      <= '0;
      accum_rst_o     <= '0;
      audio_valid_o   <= '0;
      filt_start_o    <= '0;
      accum_mux_o     <= '0;

      case (cur_state)
        STATE_IDLE: begin
          accum_rst_o   <= 1'b1;
        end

        STATE_SYN: begin
          voice_start_o <= 1'b1;
        end

        STATE_ENV: begin
          mult_in_mux_o <= 2'b00;
          env_start_o   <= 1'b1;
        end

        STATE_ENV_WAIT: begin
          mult_in_mux_o <= 2'b00;
        end

        STATE_ACCUM: begin
          accum_en_o    <= 1'b1;
          case (cur_voice)
            2'b00: accum_mux_o <= filt_en_i[0];
            2'b01: accum_mux_o <= filt_en_i[1];
            2'b10: accum_mux_o <= filt_en_i[2];
            default: ;
          endcase
        end

        STATE_FILT: begin
          mult_in_mux_o <= 2'b01;
          filt_start_o  <= 1'b1;
        end

        STATE_FILT_WAIT: begin
          mult_in_mux_o <= 2'b01;
        end

        STATE_VOL: begin
          mult_in_mux_o <= 2'b10;
          mult_start_o  <= 1'b1;
        end

        STATE_VOL_WAIT: begin
          mult_in_mux_o <= 2'b10;
        end

        STATE_DONE: begin
          audio_valid_o    <= 1'b1;
        end

        default: ;
      endcase
    end
  end

endmodule