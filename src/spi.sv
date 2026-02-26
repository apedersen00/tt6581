//-------------------------------------------------------------------------------------------------
//
//  File: spi.sv
//  Description: 4-Wire Serial Peripheral Interface (SPI) for register configuration.
//
//  Author:
//    - Andreas Pedersen
//
//-------------------------------------------------------------------------------------------------

/*
  Instantiation Template:

  spi spi_inst (
    .clk_i        (),
    .rst_ni       (),
    .sclk_i       (),
    .cs_i         (),
    .mosi_i       (),
    .miso_o       (),
    .reg_rdata_i  (),
    .reg_wdata_o  (),
    .reg_addr_o   (),
    .reg_we_o     ()
  );
*/

module spi (
  input   logic       clk_i,      // System clock (50 MHz)
  input   logic       rst_ni,     // Active low reset

  input   logic       sclk_i,     // SPI Clock
  input   logic       cs_i,       // SPI Chip select
  input   logic       mosi_i,     // SPI MOSI
  output  logic       miso_o,     // SPI MISO

  input   logic [7:0] reg_rdata_i,
  output  logic [7:0] reg_wdata_o,
  output  logic [6:0] reg_addr_o,
  output  logic       reg_we_o
);

  logic [2:0] sclk_sync;
  logic [1:0] cs_sync;
  logic [1:0] mosi_sync;

  // Re-time SPI signals to system clock
  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      sclk_sync <= '0;
      cs_sync   <= '0;
      mosi_sync <= '0;
    end else begin
      sclk_sync <= {sclk_sync[1:0], sclk_i};
      cs_sync   <= {cs_sync[0]    , cs_i};
      mosi_sync <= {mosi_sync[0]  , mosi_i};
    end
  end

  logic sclk_rise;
  assign sclk_rise = (sclk_sync[2:1] == 2'b01);

  logic sclk_fall;
  assign sclk_fall = (sclk_sync[2:1] == 2'b10);

  logic cs_active;
  assign cs_active = !cs_sync[1];

  /************************************
   * State machine
   ***********************************/
  logic [3:0] bit_cnt;
  logic [6:0] shift_reg;
  logic [7:0] data_out_reg;

  logic is_write_cmd; // 1 = Write, 0 = Read

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      bit_cnt       <= '0;
      shift_reg     <= '0;
      reg_addr_o    <= '0;
      reg_wdata_o   <= '0;
      reg_we_o      <= '0;
      is_write_cmd  <= '0;
      data_out_reg  <= '0;
    end else if (!cs_active) begin
      bit_cnt   <= '0;
      reg_we_o  <= '0;
    end else begin

      // On rising edge of SCLK
      if (sclk_rise) begin
        shift_reg <= {shift_reg[5:0], mosi_sync[1]};

        if (bit_cnt == 7) begin
          reg_addr_o    <= {shift_reg[5:0], mosi_sync[1]};
          is_write_cmd  <= {shift_reg[6]};
        end

        if (bit_cnt == 15) begin
          if (is_write_cmd) begin
            reg_wdata_o <= {shift_reg[6:0], mosi_sync[1]};
            reg_we_o    <= 1'b1;
          end
        end

        if (bit_cnt < 15) bit_cnt <= bit_cnt + 1;
      end else begin
        reg_we_o <= '0;
      end

      // On falling edge of SCLK
      if (bit_cnt == 8 && sclk_fall && !is_write_cmd) begin
        data_out_reg <= reg_rdata_i;
      end else if (sclk_fall) begin
        data_out_reg <= {data_out_reg[6:0], 1'b0};
      end
    end
  end

  assign miso_o = cs_active ? data_out_reg[7] : 1'b0;

endmodule