//-------------------------------------------------------------------------------------------------
//
//  File: envelope.sv
//  Description: Envelope generator and volume control.
//
//  Author:
//    - Andreas Pedersen
//
//-------------------------------------------------------------------------------------------------

/*
  Instantiation Template:

  envelope envelope_inst (
    .clk_i        (),
    .rst_ni       (),
    .start_i      (),
    .voice_idx_i  (),
    .gate_i       (),
    .attack_i     (),
    .decay_i      (),
    .sustain_i    (),
    .release_i    (),
    .mult_ready_i (),
    .mult_start_o (),
    .env_raw_o    (),
    .ready_o      ()
  );
*/

module envelope (
  input   logic       clk_i,
  input   logic       rst_ni,
  input   logic       start_i,      // Start processing voice_idx_i

  input   logic [1:0] voice_idx_i,  // Active voice [0-2]
  input   logic       gate_i,       // Gate control

  input   logic [3:0] attack_i,
  input   logic [3:0] decay_i,
  input   logic [3:0] sustain_i,
  input   logic [3:0] release_i,

  input   logic       mult_ready_i,
  output  logic       mult_start_o,
  output  logic [7:0] env_raw_o,

  output  logic       ready_o
);

  localparam logic [23:0] MAX_VOL = 24'hFFFFFF;

  /************************************
   * Signals and assignments
   ***********************************/
  logic [23:0]  vol_regs [2:0];   // Q8.16
  logic [23:0]  cur_vol;          // Q8.16
  logic [23:0]  nxt_vol;          // Q8.16
  logic [23:0]  sustain_vol;      // Q8.16

  logic [17:0]  attack_lut;
  logic [17:0]  decay_lut;
  logic [23:0]  attack_step;
  logic [23:0]  decay_step;
  logic [3:0]   decay_release;

  assign sustain_vol   = {sustain_i, sustain_i, 16'h0};
  assign cur_vol       = vol_regs[voice_idx_i];
  assign mult_start_o  = (cur_state == STATE_ADSR);
  assign ready_o       = (cur_state == STATE_DONE);
  assign attack_step   = {6'd0, attack_lut};
  assign decay_step    = {6'd0, decay_lut};
  assign decay_release = (cur_voice_state == STATE_DECAY) ? decay_i : release_i; 

  /************************************
   * Master state machine
   ***********************************/
  typedef enum logic [1:0] {
    STATE_IDLE,   // Idle
    STATE_ADSR,   // Init ADSR cycle
    STATE_MULT,   // Multiply
    STATE_DONE
  } state_e;

  state_e cur_state, nxt_state;

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni)  cur_state <= STATE_IDLE;
    else          cur_state <= nxt_state;
  end

  always_comb begin
    nxt_state   = cur_state;
    unique case (cur_state)
      STATE_IDLE:   nxt_state = start_i       ? STATE_ADSR  : STATE_IDLE;
      STATE_ADSR:   nxt_state = STATE_MULT;
      STATE_MULT:   nxt_state = mult_ready_i  ? STATE_DONE  : STATE_MULT;
      STATE_DONE:   nxt_state = STATE_IDLE;
      default: ;
    endcase
  end

  /************************************
   * Voice envelope state machine
   ***********************************/
  typedef enum logic [1:0] {
    STATE_ATTACK,
    STATE_DECAY,
    STATE_SUSTAIN,
    STATE_RELEASE
  } voice_state_e;

  voice_state_e voice_states [2:0];
  voice_state_e cur_voice_state, nxt_voice_state;

  assign cur_voice_state = voice_states[voice_idx_i];

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      for (int i = 0; i < 3; i++) begin
        voice_states[i] <= STATE_RELEASE;
      end
    end else if (cur_state == STATE_ADSR) begin
      voice_states[voice_idx_i] <= nxt_voice_state;
    end
  end

  always_comb begin
    nxt_voice_state = cur_voice_state;

    // Always go to release if gate goes low
    if (!gate_i && cur_voice_state != STATE_RELEASE) begin
      nxt_voice_state = STATE_RELEASE;
    end
    // Re-trigger attack if in release and gate goes high
    else if (gate_i && cur_voice_state == STATE_RELEASE) begin
      nxt_voice_state = STATE_ATTACK;
    end
    else begin
      unique case (cur_voice_state)
        STATE_ATTACK:   nxt_voice_state = (cur_vol >= MAX_VOL)      ? STATE_DECAY   : STATE_ATTACK;
        STATE_DECAY:    nxt_voice_state = (cur_vol <= sustain_vol)  ? STATE_SUSTAIN : STATE_DECAY;
        STATE_SUSTAIN:  nxt_voice_state = STATE_SUSTAIN;
        STATE_RELEASE:  nxt_voice_state = STATE_RELEASE;
        default: ;
      endcase
    end
  end

  /************************************
   * Map delays
   ***********************************/
  always_comb begin
    attack_lut = 0;
    decay_lut  = 0;

    unique case (attack_i)
      4'h0: attack_lut = 18'd83558;
      4'h1: attack_lut = 18'd20889;
      4'h2: attack_lut = 18'd10444;
      4'h3: attack_lut = 18'd6963;
      4'h4: attack_lut = 18'd4397;
      4'h5: attack_lut = 18'd2984;
      4'h6: attack_lut = 18'd2457;
      4'h7: attack_lut = 18'd2088;
      4'h8: attack_lut = 18'd1671;
      4'h9: attack_lut = 18'd668;
      4'hA: attack_lut = 18'd334;
      4'hB: attack_lut = 18'd208;
      4'hC: attack_lut = 18'd167;
      4'hD: attack_lut = 18'd55;
      4'hE: attack_lut = 18'd33;
      4'hF: attack_lut = 18'd20;
      default: ;
    endcase

    unique case (decay_release)
      4'h0: decay_lut = 18'd69630;
      4'h1: decay_lut = 18'd17407;
      4'h2: decay_lut = 18'd8702;
      4'h3: decay_lut = 18'd5802;
      4'h4: decay_lut = 18'd3662;
      4'h5: decay_lut = 18'd2485;
      4'h6: decay_lut = 18'd2047;
      4'h7: decay_lut = 18'd1740;
      4'h8: decay_lut = 18'd1392;
      4'h9: decay_lut = 18'd555;
      4'hA: decay_lut = 18'd277;
      4'hB: decay_lut = 18'd172;
      4'hC: decay_lut = 18'd137;
      4'hD: decay_lut = 18'd45;
      4'hE: decay_lut = 18'd27;
      4'hF: decay_lut = 18'd15;
    endcase
  end

  /************************************
   * Calculate volume
   ***********************************/
  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      for (int i = 0; i < 3; i++) begin
        vol_regs[i] <= 0;
      end
    end else begin
      if (cur_state == STATE_ADSR) begin
        vol_regs[voice_idx_i] <= nxt_vol;
      end
    end
  end

  logic [1:0] exp_shift;
  logic [23:0] step;

  always_comb begin
    if      (cur_vol[23]) exp_shift = 0;  // 1
    else if (cur_vol[22]) exp_shift = 1;  // 1/2
    else if (cur_vol[21]) exp_shift = 2;  // 1/4
    else                  exp_shift = 3;  // 1/8
  end

  always_comb begin
    if (nxt_voice_state == STATE_ATTACK) begin
      step = attack_step;
    end else begin
      step = (decay_step >> exp_shift) | 24'd1;
    end
  end

  always_comb begin
    nxt_vol = cur_vol;
    unique case (nxt_voice_state)
      STATE_ATTACK: begin
        // Handle clipping
        if (cur_vol + step < cur_vol) nxt_vol = MAX_VOL;
        else                          nxt_vol = cur_vol + step;
      end

      STATE_DECAY: begin
        if (cur_vol <= sustain_vol + step)  nxt_vol = sustain_vol;
        else                                nxt_vol = cur_vol - step;
      end

      STATE_SUSTAIN: begin
        nxt_vol = sustain_vol;
      end

      STATE_RELEASE: begin
        if (cur_vol <= step)  nxt_vol = 0;
        else                  nxt_vol = cur_vol - step;
      end

      default: ;
    endcase
  end

  assign env_raw_o = cur_vol[23:16];

endmodule