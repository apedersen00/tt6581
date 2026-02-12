//-------------------------------------------------------------------------------------------------
//
//  File: tt6581.sv
//  Description: Top module for the TT6581.
//
//  Author:
//    - Andreas Pedersen
//
//-------------------------------------------------------------------------------------------------

/*
  Instantiation Template:

  tt6581 tt6581_inst (
    .clk_i  (),
    .rst_ni (),
    .sclk_i (),
    .cs_i   (),
    .mosi_i (),
    .miso_o (),
    .wave_o ()
  );
*/

module tt6581 (
  input   logic       clk_i,      // System clock (50 MHz)
  input   logic       rst_ni,     // Active low reset
  input   logic       sclk_i,     // SPI Clock
  input   logic       cs_i,       // SPI Chip select
  input   logic       mosi_i,     // SPI MOSI
  output  logic       miso_o,     // SPI MISO
  output  logic [9:0] wave_o
);

  /************************************
   * Signals and assignments
   ***********************************/
  logic       sample_tick;

  // SPI and register file signals
  logic [7:0] reg_rdata;
  logic [7:0] reg_wdata;
  logic [6:0] reg_addr;
  logic       reg_we;

  logic [2:0][7:0] freq_lo_pack;
  logic [2:0][7:0] freq_hi_pack;
  logic [2:0][7:0] pw_lo_pack;
  logic [2:0][7:0] pw_hi_pack;
  logic [2:0][7:0] control_pack;
  logic [2:0][7:0] ad_pack;
  logic [2:0][7:0] sr_pack;

  logic [7:0] fc_lo;
  logic [7:0] fc_hi;
  logic [7:0] res_filt;
  logic [7:0] mode_vol;

  // Voice
  logic         voice_ready;
  logic         voice_start;
  logic [1:0]   voice_idx;
  logic [15:0]  voice_freq;
  logic [11:0]  voice_pw;
  logic [3:0]   voice_sel;
  logic [9:0]   voice_wave;

  // Envelope
  logic         env_ready;
  logic         env_start;
  logic         env_gate;
  logic [3:0]   env_attack;
  logic [3:0]   env_decay;
  logic [3:0]   env_sustain;
  logic [3:0]   env_release;
  logic [7:0]   env_raw;

  // Multiplier
  logic         mult_ready;
  logic         mult_start;
  logic         env_mult_start;
  logic         ctr_mult_start;
  logic         mult_in_mux;
  logic         mult_out_latch;
  logic         mult_rst_latch;
  logic [13:0]  mult_a_in;
  logic [7:0]   mult_b_in;
  logic [13:0]  mult_out;

  // Output
  logic [13:0]  mult_out_accum;
  logic         audio_valid;

  /************************************
   * Instances
   ***********************************/
  tick_gen tick_gen_inst (
    .clk_i          ( clk_i         ),
    .rst_ni         ( rst_ni        ),
    .tick_o         ( sample_tick   )
  );

  spi spi_inst (
    .clk_i          ( clk_i         ),
    .rst_ni         ( rst_ni        ),
    .sclk_i         ( sclk_i        ),
    .cs_i           ( cs_i          ),
    .mosi_i         ( mosi_i        ),
    .miso_o         ( miso_o        ),
    .reg_rdata_i    ( reg_rdata     ),
    .reg_wdata_o    ( reg_wdata     ),
    .reg_addr_o     ( reg_addr      ),
    .reg_we_o       ( reg_we        )
  );

  reg_file reg_file_inst (
    .clk_i              ( clk_i         ),
    .rst_ni             ( rst_ni        ),
    .addr_i             ( reg_addr      ),
    .wdata_i            ( reg_wdata     ),
    .we_i               ( reg_we        ),
    .rdata_o            ( reg_rdata     ),

    .voice_freq_lo_o    ( freq_lo_pack  ),
    .voice_freq_hi_o    ( freq_hi_pack  ),
    .voice_pw_lo_o      ( pw_lo_pack    ),
    .voice_pw_hi_o      ( pw_hi_pack    ),
    .voice_control_o    ( control_pack  ),
    .voice_ad_o         ( ad_pack       ),
    .voice_sr_o         ( sr_pack       ),

    .filter_fc_lo_o     ( fc_lo         ),
    .filter_fc_hi_o     ( fc_hi         ),
    .filter_res_filt_o  ( res_filt      ),
    .filter_mode_vol_o  ( mode_vol      )
  );

  controller controller_inst (
    .clk_i              ( clk_i           ),
    .rst_ni             ( rst_ni          ),
    .sample_tick_i      ( sample_tick     ),

    // Register file
    .freq_lo_i          ( freq_lo_pack    ),
    .freq_hi_i          ( freq_hi_pack    ),
    .pw_lo_i            ( pw_lo_pack      ),
    .pw_hi_i            ( pw_hi_pack      ),
    .control_i          ( control_pack    ),
    .ad_i               ( ad_pack         ),
    .sr_i               ( sr_pack         ),
    .fc_lo_i            (                 ),
    .fc_hi_i            (                 ),
    .res_filt_i         (                 ),
    .mode_vol_i         (                 ),

    // Voice generator
    .voice_ready_i      ( voice_ready     ),
    .voice_start_o      ( voice_start     ),
    .voice_idx_o        ( voice_idx       ),
    .voice_freq_o       ( voice_freq      ),
    .voice_pw_o         ( voice_pw        ),
    .voice_wave_o       ( voice_sel       ),

    // Envelope generator
    .env_ready_i        ( env_ready       ),
    .env_start_o        ( env_start       ),
    .env_gate_o         ( env_gate        ),
    .env_attack_o       ( env_attack      ),
    .env_decay_o        ( env_decay       ),
    .env_sustain_o      ( env_sustain     ),
    .env_release_o      ( env_release     ),

    // Multiplier
    .mult_ready_i       ( mult_ready      ),
    .mult_start_o       ( ctr_mult_start  ),
    .mult_in_mux_o      ( mult_in_mux     ),
    .mult_out_latch_o   ( mult_out_latch  ),
    .mult_rst_latch_o   ( mult_rst_latch  ),

    .audio_valid_o      ( audio_valid     )
  );

  multi_voice multi_voice_inst (
    .clk_i          ( clk_i         ),
    .rst_ni         ( rst_ni        ),
    .start_i        ( voice_start   ),
    .act_voice_i    ( voice_idx     ),
    .freq_word_i    ( voice_freq    ),
    .pw_word_i      ( voice_pw      ),
    .wave_sel_i     ( voice_sel     ),
    .ready_o        ( voice_ready   ),
    .wave_o         ( voice_wave    )
  );

  envelope envelope_inst (
    .clk_i          ( clk_i           ),
    .rst_ni         ( rst_ni          ),
    .start_i        ( env_start       ),
    .voice_idx_i    ( voice_idx       ),
    .gate_i         ( env_gate        ),
    .attack_i       ( env_attack      ),
    .decay_i        ( env_decay       ),
    .sustain_i      ( env_sustain     ),
    .release_i      ( env_release     ),
    .mult_ready_i   ( mult_ready      ),
    .mult_start_o   ( env_mult_start  ),
    .env_raw_o      ( env_raw         ),
    .ready_o        ( env_ready       )
  );

  // Mux selects between envelope (0) and volume (1) operands
  assign mult_start = env_mult_start | ctr_mult_start;
  assign mult_a_in  = mult_in_mux ? mult_out_accum : {4'd0, voice_wave};
  assign mult_b_in  = mult_in_mux ? {mode_vol[3:0], mode_vol[3:0]} : env_raw;

  mult mult_inst (
    .clk_i          ( clk_i           ),
    .rst_ni         ( rst_ni          ),
    .start_i        ( mult_start      ),
    .op_a_i         ( mult_a_in       ),
    .op_b_i         ( mult_b_in       ),
    .ready_o        ( mult_ready      ),
    .prod_o         ( mult_out        )
  );

  /************************************
   * Output accumulator
   ***********************************/

  logic [9:0] wave_hold;

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      mult_out_accum <= '0;
      wave_hold      <= '0;
    end else begin
      
      if (mult_out_latch) begin
        mult_out_accum <= mult_out_accum + mult_out;
      end

      if (audio_valid) begin
        if (mult_out > 14'd1023) begin
          wave_hold <= 10'd1023;
        end else begin
          wave_hold <= mult_out[9:0];
        end
      end else if (mult_rst_latch) begin
        mult_out_accum <= '0;
      end
    end
  end

  assign wave_o = wave_hold;

endmodule