// buggy_fsm_unreachable.v
// RTL_E006 fixture: state DEAD is never reached from any transition.
module buggy_fsm_unreachable (
    input  wire clk,
    input  wire rst_n,
    input  wire go,
    output reg  done
);
    typedef enum logic [1:0] {
        IDLE  = 2'b00,
        RUN   = 2'b01,
        DONE  = 2'b10,
        DEAD  = 2'b11   // unreachable — no transition leads here
    } state_t;

    state_t state, next;

    // State register
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) state <= IDLE;
        else        state <= next;
    end

    // Next-state logic
    always_comb begin
        next = state;
        done = 1'b0;
        case (state)
            IDLE: if (go) next = RUN;
            RUN:  next = DONE;
            DONE: begin done = 1'b1; next = IDLE; end
            // DEAD: never assigned — unreachable
            default: next = IDLE;
        endcase
    end
endmodule
