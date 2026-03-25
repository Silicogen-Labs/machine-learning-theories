// CLEAN: Correct RTL — should produce zero findings (or INFO-only).
// This is the ground-truth clean reference.

module clean_counter #(
    parameter WIDTH = 8
)(
    input  wire          clk,
    input  wire          rst_n,
    input  wire          enable,
    output reg  [WIDTH-1:0] count,
    output reg           overflow
);

// Correct: always_ff with non-blocking assignments and proper reset
always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        count    <= {WIDTH{1'b0}};
        overflow <= 1'b0;
    end else if (enable) begin
        if (count == {WIDTH{1'b1}}) begin
            count    <= {WIDTH{1'b0}};
            overflow <= 1'b1;
        end else begin
            count    <= count + 1'b1;
            overflow <= 1'b0;
        end
    end
end

endmodule
