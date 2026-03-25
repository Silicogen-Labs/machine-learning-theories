// buggy_multi_case.v
//
// Fixture: verifies that RTL_W001 (missing default in case) fires correctly
// when there are TWO case statements in a single always block — the first
// missing a default, the second having one.
//
// Bug H regression: the old depth counter used s.count("case") which
// matched the "case" substring inside "endcase", causing the depth never
// to return to 0 properly.  The fix uses word-boundary regex.
//
// Expected findings:
//   RTL_W001  — first case statement has no default
//   (second case has default → should NOT produce an extra RTL_W001)

module buggy_multi_case (
    input  wire [1:0] sel,
    input  wire [1:0] mode,
    output reg  [7:0] out_a,
    output reg  [7:0] out_b
);

    always_comb begin
        // First case: missing default → should fire RTL_W001
        case (sel)
            2'b00: out_a = 8'hAA;
            2'b01: out_a = 8'hBB;
            2'b10: out_a = 8'hCC;
            // 2'b11 not covered, no default
        endcase

        // Second case: has default → should NOT fire RTL_W001
        case (mode)
            2'b00: out_b = 8'h11;
            2'b01: out_b = 8'h22;
            default: out_b = 8'hFF;
        endcase
    end

endmodule
