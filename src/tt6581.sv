/*
 * File: tt_um_andreasp00.sv
 * Description: Tiny Tapeout Top Module for SID-like Synth
 */

`default_nettype none

module tt_um_andreasp00 (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // IOs: Input path
    output wire [7:0] uio_out,  // IOs: Output path
    output wire [7:0] uio_oe,   // IOs: Enable path (active high: 0=input, 1=output)
    input  wire       ena,      // will go high when the design is enabled
    input  wire       clk,      // clock
    input  wire       rst_n     // reset_n - low to reset
);

    wire sclk = ui_in[0];
    wire cs   = ui_in[1];
    wire mosi = ui_in[2];
    
    wire miso;
    assign uo_out[0] = miso;
    
    assign uio_out = 8'b0;
    assign uio_oe  = 8'b0;

    logic [7:0] reg_rdata;
    logic [7:0] reg_wdata;
    logic [6:0] reg_addr;
    logic       reg_we;
    logic       sample_tick;

    logic [2:0][7:0] freq_lo_pack, freq_hi_pack;
    logic [2:0][7:0] pw_lo_pack, pw_hi_pack;
    logic [2:0][7:0] control_pack, ad_pack, sr_pack;

    logic        voice_ready;
    logic [9:0]  voice_wave;
    logic        voice_start;
    logic [1:0]  voice_idx;
    logic [15:0] voice_freq;
    logic [11:0] voice_pw;
    logic [3:0]  voice_sel;
      
    logic         env_ready;
    logic         env_start;
    logic         env_gate;
    logic [9:0]   env_wave;
    logic [3:0]   env_attack;
    logic [3:0]   env_decay;
    logic [3:0]   env_sustain;
    logic [3:0]   env_release;

    logic [15:0] mix_out;
    logic        mix_valid;

    tick_gen tick_gen_inst (
        .clk_i  (clk),
        .rst_ni (rst_n),
        .tick_o (sample_tick)
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
    .voice_wave_i   ( env_wave      ),
    .voice_start_o  ( voice_start   ),
    .voice_idx_o    ( voice_idx     ),
    .voice_freq_o   ( voice_freq    ),
    .voice_pw_o     ( voice_pw      ),
    .voice_wave_o   ( voice_sel     ),

    // Envelope generator
    .env_ready_i    ( env_ready     ),
    .env_start_o    ( env_start     ),
    .env_gate_o     ( env_gate      ),
    .env_attack_o   ( env_attack    ),
    .env_decay_o    ( env_decay     ),
    .env_sustain_o  ( env_sustain   ),
    .env_release_o  ( env_release   ),

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

  envelope envelope_inst (
    .clk_i          ( clk           ),
    .rst_ni         ( rst_n         ),
    .start_i        ( env_start     ),
    .wave_i         ( voice_wave    ),
    .voice_idx_i    ( voice_idx     ),
    .gate_i         ( env_gate      ),
    .attack_i       ( env_attack    ),
    .decay_i        ( env_decay     ),
    .sustain_i      ( env_sustain   ),
    .release_i      ( env_release   ),
    .ready_o        ( env_ready     ),
    .wave_o         ( env_wave      )
  );

    assign uo_out[7:1] = mix_out[15:9];

    wire _unused_ok = &{
        ena,
        uio_in,     // Not using bidirectional pins
        ui_in[7:3], // Not using pins 3-7
        mix_valid,  // Not triggering anything with valid yet
        1'b0
    };

endmodule