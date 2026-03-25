module clean_registered_feedback(
    input wire clk,
    input wire rst_n,
    input wire d,
    output reg q
);
    reg feedback;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            feedback <= 1'b0;
            q <= 1'b0;
        end else begin
            feedback <= q;
            q <= feedback ^ d;
        end
    end
endmodule
