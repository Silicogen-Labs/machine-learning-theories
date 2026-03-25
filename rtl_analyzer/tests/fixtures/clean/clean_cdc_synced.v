// clean_cdc_synced.v
// Two-clock design with a 2FF synchroniser — no RTL_W007.
module clean_cdc_synced (
    input  wire clk_a,
    input  wire clk_b,
    input  wire rst_n,
    input  wire data_in,
    output reg  data_out
);
    reg data_reg_a;
    reg sync_ff1, sync_ff2;   // 2FF synchroniser in clk_b domain

    always @(posedge clk_a or negedge rst_n) begin
        if (!rst_n) data_reg_a <= 1'b0;
        else        data_reg_a <= data_in;
    end

    // Synchroniser chain
    always @(posedge clk_b or negedge rst_n) begin
        if (!rst_n) begin
            sync_ff1 <= 1'b0;
            sync_ff2 <= 1'b0;
        end else begin
            sync_ff1 <= data_reg_a;
            sync_ff2 <= sync_ff1;
        end
    end

    always @(posedge clk_b or negedge rst_n) begin
        if (!rst_n) data_out <= 1'b0;
        else        data_out <= sync_ff2;
    end
endmodule
