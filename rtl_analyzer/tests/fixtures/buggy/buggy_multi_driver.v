// BUGGY: Multiple drivers on the same signal
// Expected findings:
//   RTL_E003 (multi-driver) — 'data_out' driven from both an assign and an always block
//
// Verilator reference: MULTIDRIVEN
// SpyGlass reference:  W14 — multiple drivers
// IEEE 1800-2017:      §10.3.2 — only one driver per net allowed (wire)

module buggy_multi_driver (
    input  wire       clk,
    input  wire       en,
    input  wire [7:0] data_in,
    output reg  [7:0] data_out
);

// Driver 1: continuous assignment
assign data_out = 8'h00;   // BUG: first driver

// Driver 2: always block — creates contention with assign above
always @(posedge clk) begin
    if (en)
        data_out <= data_in;   // BUG: second driver
end

endmodule
