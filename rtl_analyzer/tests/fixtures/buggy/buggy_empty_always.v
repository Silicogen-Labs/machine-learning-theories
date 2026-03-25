// buggy_empty_always.v
//
// Fixture: verifies that RTL_I003 fires on an always block that contains
// no statements — dead code left behind after a refactor.
//
// Expected findings:
//   RTL_I003  — empty always block

module buggy_empty_always (
    input  wire clk,
    input  wire rst_n,
    output reg  q
);

    // Legitimate sequential block
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            q <= 1'b0;
        else
            q <= ~q;
    end

    // Accidentally empty block — dead code
    always @(posedge clk) begin
    end

endmodule
