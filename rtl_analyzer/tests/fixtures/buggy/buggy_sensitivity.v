// BUGGY: Incomplete sensitivity list
// Expected findings:
//   RTL_W003 (incomplete sensitivity list) — 'b' and 'sel' are used but missing from @(a)
//
// Verilator reference: style warning for incomplete @(...) list
// SpyGlass reference:  W28 — signal missing from sensitivity list
// IEEE 1800-2017:      §9.4.2.2 — always_comb automatically infers complete sensitivity

module buggy_sensitivity (
    input  wire a,
    input  wire b,
    input  wire sel,
    output reg  y
);

// BUG: 'b' and 'sel' are missing from the sensitivity list.
// Simulation will not re-evaluate when b or sel change.
// Synthesis treats this as always_comb anyway — sim/synth mismatch.
always @(a) begin
    if (sel)
        y = a;
    else
        y = b;
end

endmodule
