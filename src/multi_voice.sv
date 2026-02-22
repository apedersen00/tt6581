//-------------------------------------------------------------------------------------------------
//
//  File: multi_voice.sv
//  Description: Sequential multi-voice generator supporting 16 voices.
//
//  Author:
//    - Andreas Pedersen
//
//-------------------------------------------------------------------------------------------------

/*
  Instantiation Template:

  multi_voice multi_voice_inst (
    .clk_i          (),
    .rst_ni         (),
    .start_i        (),
    .act_voice_i    (),
    .freq_word_i    (),
    .pw_word_i      (),
    .wave_sel_i     (),
    .ready_o        (),
    .wave_o         ()
  );
*/

module multi_voice (
  input   logic         clk_i,        // 50 MHz
  input   logic         rst_ni,       // Active low reset
  input   logic         start_i,      // Start generating voice
  input   logic [1:0]   act_voice_i,  // Active voice 0..2
  input   logic [15:0]  freq_word_i,  // Frequency control word
  input   logic [11:0]  pw_word_i,    // Pulse width control
  input   logic [3:0]   wave_sel_i,   // 0010: Saw, 0001: Tri, 0100: Pulse, 1000: Noise
  input   logic         sync_i,
  input   logic         ring_mod_i,
  output  logic         ready_o,      // Voice is generated
  output  logic signed  [9:0]   wave_o        // Audio output
);

  /************************************
   * Registers (voice states)
   ***********************************/
  logic         [18:0]  phase_regs [2:0];
  logic         [22:0]  lfsr_regs [2:0];
  logic signed  [9:0]   wave_saw, wave_tri, wave_pulse, wave_noise;

  logic [1:0] phase_last_msb [2:0];

  logic [18:0]  cur_phase, nxt_phase;
  logic [22:0]  cur_lfsr, nxt_lfsr;
  logic         noise_en;

  /************************************
   * State machine
   ***********************************/
  typedef enum logic [1:0] {
    STATE_READY,
    STATE_BUSY,
    STATE_WRITE
  } state_e;

  state_e cur_state, nxt_state;

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni)  cur_state <= STATE_READY;
    else          cur_state <= nxt_state;
  end

  always_comb begin
    nxt_state = STATE_READY;
    unique case (cur_state)
      STATE_READY: begin
        if (start_i) nxt_state = STATE_BUSY;
        else         nxt_state = STATE_READY;
      end
      STATE_BUSY:   nxt_state = STATE_WRITE;
      STATE_WRITE:  nxt_state = STATE_READY;
      default     : ;
    endcase
  end

  /************************************
   * Reset and writeback
   ***********************************/
  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      ready_o <= 1'b0;

      for (int i = 0; i < 3; i++) begin
        phase_regs[i]     <= '0;
        lfsr_regs[i]      <= 23'h7FFFFF;
        phase_last_msb[i] <= 2'b00;
      end

    end else begin
      if (cur_state == STATE_WRITE) begin
        phase_regs[act_voice_i] <= nxt_phase;
        lfsr_regs[act_voice_i]  <= nxt_lfsr;
        phase_last_msb[act_voice_i] <= {phase_last_msb[act_voice_i][0], nxt_phase[18]};
        ready_o <= 1'b1;
      end else begin
        ready_o <= 1'b0;
      end
    end
  end

  /************************************
   * Wave generation
   ***********************************/
  assign cur_phase = phase_regs[act_voice_i];
  assign cur_lfsr  = lfsr_regs[act_voice_i];

  // TODO: Fix this. Instead of scaling freq_word, fix the calculation and bits required
  // due to now only updating it 50 kHz (on sample_tick)
  logic [1:0] prev_voice;
  always_comb begin
    unique case (act_voice_i)
      2'd0:    prev_voice = 2'd2;
      2'd1:    prev_voice = 2'd0;
      2'd2:    prev_voice = 2'd1;
      default: prev_voice = 2'd2;
    endcase
  end

  logic prev_voice_rising_edge;
  assign prev_voice_rising_edge = (phase_last_msb[prev_voice] == 2'b01);

  always_comb begin
    nxt_phase = cur_phase + {3'd0, freq_word_i};
    if (sync_i && prev_voice_rising_edge) begin
      nxt_phase = '0;
    end
  end

  // Ring modulation
  logic tri_fold;
  assign tri_fold = ring_mod_i ? (nxt_phase[18] ^ phase_regs[prev_voice][18]) : nxt_phase[18];

  assign wave_saw   = {nxt_phase[18], nxt_phase[17:9]};
  assign wave_tri   = (tri_fold ? ~nxt_phase[17:8] : nxt_phase[17:8]) ^ 10'h200;
  assign wave_pulse = (nxt_phase[18:7] >= pw_word_i) ? 10'sd511 : -10'sd512;

  assign noise_en = (cur_phase[9] == 1'b0 && nxt_phase[9] == 1'b1);

  always_comb begin
    nxt_lfsr = cur_lfsr;
    if (noise_en) nxt_lfsr = {cur_lfsr[21:0], cur_lfsr[22] ^ cur_lfsr[17]};
  end

  logic [7:0] sid_noise_8bit;
  assign sid_noise_8bit = {
    cur_lfsr[20], cur_lfsr[18], cur_lfsr[14], cur_lfsr[11],
    cur_lfsr[9] , cur_lfsr[5] , cur_lfsr[2] , cur_lfsr[0]
  };

  assign wave_noise = {~sid_noise_8bit[7], sid_noise_8bit[6:0], 2'b00};

  /************************************
   * MUX output
   ***********************************/
  always_comb begin
    unique case (wave_sel_i)
      4'b0001: wave_o = wave_tri;
      4'b0010: wave_o = wave_saw;
      4'b0100: wave_o = wave_pulse;
      4'b1000: wave_o = wave_noise;
      default: wave_o = '0;
    endcase
  end

endmodule