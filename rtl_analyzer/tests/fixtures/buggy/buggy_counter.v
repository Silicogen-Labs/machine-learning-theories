// BUGGY: Multiple issues deliberately injected for testing.
// Expected findings:
//   RTL_E004 (blocking in ff)  - line 22
//   RTL_E001 (latch inference) - line 30
//   RTL_W001 (missing default) - line 40
//   RTL_W005 (initial block)   - line 12

module buggy_counter #(
    parameter WIDTH = 8
)(
    input  wire          clk,
    input  wire          rst_n,
    input  wire          enable,
    input  wire [3:0]    load_val,
    output reg  [WIDTH-1:0] count,
    output reg           overflow
);

// RTL_W005: initial block (sim/synth mismatch)
initial begin
    count = 0;
    overflow = 0;
end

// RTL_E004: blocking assignment in sequential always block
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        count = 0;          // BUG: should be <=
        overflow = 0;       // BUG: should be <=
    end else if (enable) begin
        count = count + 1;  // BUG: should be <=
    end
end

// RTL_E001: combinational block with if but no else -> latch on 'overflow'
always @(*) begin
    if (count == 8'hFF)
        overflow = 1'b1;
    // MISSING: else overflow = 1'b0;  <- latch!
end

// RTL_W001: case without default
always @(posedge clk) begin
    case (load_val)
        4'h0: count <= 8'h00;
        4'h1: count <= 8'h10;
        4'hF: count <= 8'hFF;
        // MISSING: default
    endcase
end

endmodule
