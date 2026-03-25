// buggy_fsm_no_default.sv
// RTL_W006 fixture: FSM next-state logic has no default branch.
module buggy_fsm_no_default (
    input  logic clk,
    input  logic rst_n,
    input  logic go,
    output logic done
);
    typedef enum logic [1:0] {IDLE, RUN, DONE} state_t;
    state_t state, next;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) state <= IDLE;
        else        state <= next;
    end

    // No default: if state is 2'b11 (unencoded), next is X
    always_comb begin
        next = IDLE;
        done = 1'b0;
        case (state)
            IDLE: if (go) next = RUN;
            RUN:  next = DONE;
            DONE: begin done = 1'b1; next = IDLE; end
            // deliberately no default
        endcase
    end
endmodule
