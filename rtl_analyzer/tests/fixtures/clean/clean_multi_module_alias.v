module first_module(output wire a, input wire b);
    assign a = b;
endmodule

module second_module(output wire b, input wire a);
    assign b = a;
endmodule
