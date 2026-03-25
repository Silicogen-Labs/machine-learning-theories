// BUGGY: Unused signals and undriven outputs
// Expected findings:
//   RTL_I001 (unused signal)   — 'debug_val' declared but never read
//   RTL_I002 (undriven signal) — 'result' is read in an expression but never assigned
//
// Verilator reference: UNUSED (W240), UNDRIVEN (W01)
// SpyGlass reference:  W240 — unused signal, W01 — undriven output

module buggy_unused (
    input  wire [7:0] a,
    input  wire [7:0] b,
    output reg  [7:0] result,
    output reg  [7:0] sum
);

// BUG: 'debug_val' is declared and never used anywhere (RTL_I001)
reg [7:0] debug_val;

// 'result' is used on the RHS (read) but never assigned — undriven output (RTL_I002)
always @(*) begin
    sum = a + b + result;   // result is read here but never driven
end

endmodule
