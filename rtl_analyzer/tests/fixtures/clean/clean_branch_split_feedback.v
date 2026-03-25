module clean_branch_split_feedback(
    input wire sel,
    output reg a,
    output reg b
);
    always @(*) begin
        if (sel)
            a = b;
        else
            b = a;
    end
endmodule
