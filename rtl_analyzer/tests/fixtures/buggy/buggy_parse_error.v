// buggy_parse_error.v
//
// Fixture: a file with a deliberate syntax error (missing endmodule) to
// verify that pyslang parse errors are surfaced as WARNING findings by the
// engine, rather than silently ignored.
//
// Expected behaviour:
//   engine.analyze_file(this_file) → at least one Finding with
//   severity == WARNING whose message references a parse/syntax error.

module buggy_parse_error (
    input  wire clk,
    output reg  q
);

    always @(posedge clk) begin
        q <= ~q;
    end

// deliberately missing endmodule — pyslang should report a syntax error
