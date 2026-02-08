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

module tt_um_andreasp00 (
  input   logic       clk,        // System clock (50 MHz)
  input   logic       rst_n,      // Active low reset
  input   logic       sclk,       // SPI Clock
  input   logic       cs,         // SPI Chip select
  input   logic       mosi,       // SPI MOSI
  output  logic       miso,       // SPI MISO
  output  logic [9:0] wave
);

  // Internal signals
  logic [7:0] reg_rdata;
  logic [7:0] reg_wdata;
  logic [6:0] reg_addr;
  logic       reg_we;
  logic       sample_tick;

  // Packed arrays from reg_file
  logic [15:0][7:0] freq_lo_pack;
  logic [15:0][7:0] freq_hi_pack;
  logic [15:0][7:0] pw_lo_pack;
  logic [15:0][7:0] pw_hi_pack;
  logic [15:0][7:0] control_pack;
  logic [15:0][7:0] ad_pack;
  logic [15:0][7:0] sr_pack;

  // Voice signals
  logic         voice_ready;
  logic [9:0]   voice_wave;
  logic         voice_start;
  logic [3:0]   voice_idx;
  logic [15:0]  voice_freq;
  logic [11:0]  voice_pw;
  logic [3:0]   voice_sel;

  // Mix
  logic [15:0] mix_out;
  logic        mix_valid;

  tick_gen tick_gen_inst (
    .clk_i          ( clk           ),
    .rst_ni         ( rst_n         ),
    .tick_o         ( sample_tick   )
  );

  spi spi_inst (
    .clk_i          ( clk           ),
    .rst_ni         ( rst_n         ),
    .sclk_i         ( sclk          ),
    .cs_i           ( cs            ),
    .mosi_i         ( mosi          ),
    .miso_o         ( miso          ),
    .reg_rdata_i    ( reg_rdata     ),
    .reg_wdata_o    ( reg_wdata     ),
    .reg_addr_o     ( reg_addr      ),
    .reg_we_o       ( reg_we        )
  );

  reg_file reg_file_inst (
    .clk_i          ( clk           ),
    .rst_ni         ( rst_n         ),
    .addr_i         ( reg_addr      ),
    .wdata_i        ( reg_wdata     ),
    .we_i           ( reg_we        ),
    .rdata_o        ( reg_rdata     ),
    .freq_lo_o      ( freq_lo_pack  ),
    .freq_hi_o      ( freq_hi_pack  ),
    .pw_lo_o        ( pw_lo_pack    ),
    .pw_hi_o        ( pw_hi_pack    ),
    .control_o      ( control_pack  ),
    .ad_o           ( ad_pack       ),
    .sr_o           ( sr_pack       )
  );

  controller controller_inst (
    .clk_i          ( clk           ),
    .rst_ni         ( rst_n         ),
    .sample_tick_i  ( sample_tick   ),

    // Register file
    .freq_lo_i      ( freq_lo_pack  ),
    .freq_hi_i      ( freq_hi_pack  ),
    .pw_lo_i        ( pw_lo_pack    ),
    .pw_hi_i        ( pw_hi_pack    ),
    .control_i      ( control_pack  ),
    .ad_i           ( ad_pack       ),
    .sr_i           ( sr_pack       ),

    // Voice generator
    .voice_ready_i  ( voice_ready   ),
    .voice_wave_i   ( voice_wave    ),
    .voice_start_o  ( voice_start   ),
    .voice_idx_o    ( voice_idx     ),
    .voice_freq_o   ( voice_freq    ),
    .voice_pw_o     ( voice_pw      ),
    .voice_wave_o   ( voice_sel     ),

    .audio_valid_o  ( mix_valid     ),
    .audio_o        ( mix_out       )
  );

  multi_voice multi_voice_inst (
    .clk_i          ( clk           ),
    .rst_ni         ( rst_n         ),
    .start_i        ( voice_start   ),
    .act_voice_i    ( voice_idx     ),
    .freq_word_i    ( voice_freq    ),
    .pw_word_i      ( voice_pw      ),
    .wave_sel_i     ( voice_sel     ),
    .ready_o        ( voice_ready   ),
    .wave_o         ( voice_wave    )
  );

  assign wave = mix_out[9:0];

endmodule