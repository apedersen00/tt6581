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
    .wave_o ()  // 1-bit PDM
  );
*/

module tt6581 (
  input   logic       clk_i,      // System clock (50 MHz)
  input   logic       rst_ni,     // Active low reset
  input   logic       sclk_i,     // SPI Clock
  input   logic       cs_i,       // SPI Chip select
  input   logic       mosi_i,     // SPI MOSI
  output  logic       miso_o,     // SPI MISO
  output  logic       wave_o      // Delta-Sigma PDM output
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

  logic [23:0] freq_lo_pack;
  logic [23:0] freq_hi_pack;
  logic [23:0] pw_lo_pack;
  logic [23:0] pw_hi_pack;
  logic [23:0] control_pack;
  logic [23:0] ad_pack;
  logic [23:0] sr_pack;

  // Voice
  logic         voice_ready;
  logic         voice_start;
  logic [1:0]   voice_idx;
  logic [15:0]  voice_freq;
  logic [11:0]  voice_pw;
  logic [3:0]   voice_sel;
  logic [9:0]   voice_wave;
  logic         voice_sync;
  logic         voice_ring_mod;

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
  logic                mult_ready;
  logic                mult_start;
  logic                env_mult_start;
  logic                ctr_mult_start;
  logic [1:0]          mult_in_mux;
  logic                accum_en;
  logic                accum_rst;
  logic signed [23:0]  mult_a_in;
  logic signed [15:0]  mult_b_in;
  logic signed [39:0]  mult_product;

  // SVF
  logic [7:0] filt_f_lo;
  logic [7:0] filt_f_hi;
  logic [7:0] filt_q_lo;
  logic [7:0] filt_q_hi;
  logic [7:0] filt_en_mode;
  logic [7:0] filt_volume;

  // Output
  logic signed [13:0]  bypass_accum;
  logic signed [13:0]  filter_accum;
  logic         audio_valid;

  /************************************
   * Instances
   ***********************************/
  tick_gen tick_gen_inst (
    .clk_i              ( clk_i           ),
    .rst_ni             ( rst_ni          ),
    .tick_o             ( sample_tick     )
  );

  spi spi_inst (
    .clk_i              ( clk_i           ),
    .rst_ni             ( rst_ni          ),
    .sclk_i             ( sclk_i          ),
    .cs_i               ( cs_i            ),
    .mosi_i             ( mosi_i          ),
    .miso_o             ( miso_o          ),
    .reg_rdata_i        ( reg_rdata       ),
    .reg_wdata_o        ( reg_wdata       ),
    .reg_addr_o         ( reg_addr        ),
    .reg_we_o           ( reg_we          )
  );

  reg_file reg_file_inst (
    .clk_i              ( clk_i           ),
    .rst_ni             ( rst_ni          ),
    .addr_i             ( reg_addr        ),
    .wdata_i            ( reg_wdata       ),
    .we_i               ( reg_we          ),
    .rdata_o            ( reg_rdata       ),

    .voice_freq_lo_o    ( freq_lo_pack    ),
    .voice_freq_hi_o    ( freq_hi_pack    ),
    .voice_pw_lo_o      ( pw_lo_pack      ),
    .voice_pw_hi_o      ( pw_hi_pack      ),
    .voice_control_o    ( control_pack    ),
    .voice_ad_o         ( ad_pack         ),
    .voice_sr_o         ( sr_pack         ),

    .filter_f_lo_o      ( filt_f_lo       ),
    .filter_f_hi_o      ( filt_f_hi       ),
    .filter_q_lo_o      ( filt_q_lo       ),
    .filter_q_hi_o      ( filt_q_hi       ),
    .filter_en_mode_o   ( filt_en_mode    ),
    .filter_volume_o    ( filt_volume     )
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

    // Voice generator
    .voice_ready_i      ( voice_ready     ),
    .voice_start_o      ( voice_start     ),
    .voice_idx_o        ( voice_idx       ),
    .voice_freq_o       ( voice_freq      ),
    .voice_pw_o         ( voice_pw        ),
    .voice_wave_o       ( voice_sel       ),
    .voice_sync_o       ( voice_sync      ),
    .voice_ring_mod_o   ( voice_ring_mod  ),

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

    .filt_en_i          ( filt_en_mode[5:3] ),
    .filt_ready_i       ( svf_ready       ),
    .filt_start_o       ( svf_start       ),

    // Output
    .accum_en_o         ( accum_en        ),
    .accum_rst_o        ( accum_rst       ),
    .accum_mux_o        ( accum_in_mux    ),

    .audio_valid_o      ( audio_valid     )
  );

  multi_voice multi_voice_inst (
    .clk_i              ( clk_i           ),
    .rst_ni             ( rst_ni          ),
    .start_i            ( voice_start     ),
    .act_voice_i        ( voice_idx       ),
    .freq_word_i        ( voice_freq      ),
    .pw_word_i          ( voice_pw        ),
    .wave_sel_i         ( voice_sel       ),
    .sync_i             ( voice_sync      ),
    .ring_mod_i         ( voice_ring_mod  ),  
    .ready_o            ( voice_ready     ),
    .wave_o             ( voice_wave      )
  );

  envelope envelope_inst (
    .clk_i              ( clk_i           ),
    .rst_ni             ( rst_ni          ),
    .start_i            ( env_start       ),
    .voice_idx_i        ( voice_idx       ),
    .gate_i             ( env_gate        ),
    .attack_i           ( env_attack      ),
    .decay_i            ( env_decay       ),
    .sustain_i          ( env_sustain     ),
    .release_i          ( env_release     ),
    .mult_ready_i       ( mult_ready      ),
    .mult_start_o       ( env_mult_start  ),
    .env_raw_o          ( env_raw         ),
    .ready_o            ( env_ready       )
  );

  logic svf_start;
  logic [2:0] filt_sel;
  logic signed [23:0] svf_mult_a;
  logic signed [15:0] svf_mult_b;
  logic svf_mult_start;
  logic svf_ready;
  logic signed [13:0] svf_out;
  logic accum_in_mux;

  assign filt_sel = filt_en_mode[2:0];

  svf svf_inst (
    .clk_i              ( clk_i           ),
    .rst_ni             ( rst_ni          ),
    .start_i            ( svf_start       ),
    .filt_sel_i         ( filt_sel        ),
    .wave_i             ( filter_accum    ),
    .coeff_f_i          ( {filt_f_hi, filt_f_lo}  ),
    .coeff_q_i          ( {filt_q_hi, filt_q_lo}  ),
    .mult_ready_i       ( mult_ready      ),
    .mult_prod_i        ( mult_product    ),
    .mult_a_o           ( svf_mult_a      ),
    .mult_b_o           ( svf_mult_b      ),
    .mult_start_o       ( svf_mult_start  ),
    .ready_o            ( svf_ready       ),
    .wave_o             ( svf_out         )
  );

  // Envelope, controller and SVF share multiplier
  assign mult_start = env_mult_start | ctr_mult_start | svf_mult_start;

  logic signed [13:0] svf_bypass_sum;
  assign svf_bypass_sum = svf_out + bypass_accum;

  // Multiplier input MUX
  always_comb begin
    mult_a_in = '0;
    mult_b_in = '0;

    unique case (mult_in_mux)
      2'b00:  mult_a_in = {{14{voice_wave[9]}}, voice_wave};
      2'b01:  mult_a_in = svf_mult_a;
      2'b10:  mult_a_in = {{10{svf_bypass_sum[13]}}, svf_bypass_sum};
      default: ;
    endcase

    unique case (mult_in_mux)
      2'b00:  mult_b_in = {8'd0, env_raw};
      2'b01:  mult_b_in = svf_mult_b;
      2'b10:  mult_b_in = {8'd0, filt_volume};
      default: ;
    endcase
  end

  mult mult_inst (
    .clk_i          ( clk_i           ),
    .rst_ni         ( rst_ni          ),
    .start_i        ( mult_start      ),
    .op_a_i         ( mult_a_in       ),
    .op_b_i         ( mult_b_in       ),
    .ready_o        ( mult_ready      ),
    .prod_o         ( mult_product    )
  );

  /************************************
   * Output accumulator
   ***********************************/
  logic signed [13:0] mult_out;
  assign mult_out = mult_product[21:8];

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      filter_accum <= '0;
      bypass_accum <= '0;
    end else if (accum_rst) begin
      filter_accum <= '0;
      bypass_accum <= '0;
    end else if (accum_en) begin
      unique case (accum_in_mux)
        1'b0: bypass_accum <= bypass_accum + mult_out;
        1'b1: filter_accum <= filter_accum + mult_out;
        default: ;
      endcase
    end
  end

  delta_sigma delta_sigma_inst (
    .clk_i          ( clk_i       ),
    .rst_ni         ( rst_ni      ),
    .audio_valid_i  ( audio_valid ),
    .audio_i        ( mult_out    ),
    .wave_o         ( wave_o      )
  );

endmodule