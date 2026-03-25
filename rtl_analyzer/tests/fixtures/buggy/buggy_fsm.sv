// BUGGY: Blocking in always_ff, non-blocking in always_comb, width mismatch
// Expected findings:
//   RTL_E004 (blocking in ff)         - lines inside always_ff
//   RTL_E005 (non-blocking in comb)   - line inside always_comb
//   RTL_W002 (width mismatch)         - explicit literal truncation
//   RTL_W004 (missing reset on FSM)   - always_ff with state, no reset

module buggy_fsm (
    input  wire       clk,
    input  wire       req,
    output reg  [1:0] state,
    output reg  [3:0] out_data
);

typedef enum logic [1:0] {
    IDLE  = 2'b00,
    FETCH = 2'b01,
    EXEC  = 2'b10,
    DONE  = 2'b11
} state_t;

// RTL_E004: blocking in sequential, RTL_W004: no reset
always_ff @(posedge clk) begin
    case (state)
        IDLE:  if (req) state = FETCH;   // BUG: blocking in ff
        FETCH: state = EXEC;             // BUG: blocking in ff
        EXEC:  state = DONE;             // BUG: blocking in ff
        DONE:  state = IDLE;             // BUG: blocking in ff
    endcase
end

// RTL_E005: non-blocking in combinational block
always_comb begin
    out_data <= 4'b0000;   // BUG: non-blocking in comb
    if (state == FETCH)
        out_data <= 4'hA;  // BUG: non-blocking in comb
end

// RTL_W002: 8-bit literal assigned into 4-bit signal
always_comb begin
    out_data = 8'hFF;   // BUG: 8-bit into 4-bit, truncates upper nibble
end

endmodule
