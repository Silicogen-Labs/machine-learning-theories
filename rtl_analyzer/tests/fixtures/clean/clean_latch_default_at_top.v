// clean_latch_default_at_top.v
//
// Fixture: verifies that RTL_E001 (latch inference) does NOT fire when
// every signal assigned inside the if branch already has an unconditional
// default assignment at the top of the always block.
//
// Pattern:
//   always_comb begin
//     x = 0;           // unconditional default — no latch possible
//     if (a) x = 1;    // override — all paths covered
//   end
//
// Correct RTL — no latch.  Any tool that flags this is producing a false
// positive.  Verilator --lint-only: PASS.  SpyGlass W415: PASS.

module clean_latch_default_at_top (
    input  wire a,
    input  wire b,
    output reg  x,
    output reg  y
);

    // x has a default before the if — no latch.
    always_comb begin
        x = 1'b0;
        if (a)
            x = 1'b1;
    end

    // y also pre-defaulted — two-input mux, no latch.
    always_comb begin
        y = 1'b0;
        if (b)
            y = a;
    end

endmodule
