// buggy_cdc.v
// RTL_W007 fixture: data_in is clocked by clk_a; it is read directly in
// the clk_b domain with no synchroniser flip-flops in between.
module buggy_cdc (
    input  wire clk_a,
    input  wire clk_b,
    input  wire rst_n,
    input  wire data_in,     // driven in clk_a domain
    output reg  data_out     // sampled in clk_b domain — CDC hazard
);
    reg data_reg_a;

    // clk_a domain: register data_in
    always @(posedge clk_a or negedge rst_n) begin
        if (!rst_n) data_reg_a <= 1'b0;
        else        data_reg_a <= data_in;
    end

    // clk_b domain: reads data_reg_a directly — no synchroniser
    always @(posedge clk_b or negedge rst_n) begin
        if (!rst_n) data_out <= 1'b0;
        else        data_out <= data_reg_a;   // RTL_W007: no sync
    end
endmodule
