module buggy_combo_loop(input wire x, output wire y);
    wire a;
    wire b;
    assign a = b;
    assign b = a;
    assign y = a ^ x;
endmodule
