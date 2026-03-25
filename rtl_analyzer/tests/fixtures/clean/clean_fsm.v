// CLEAN: Correct 3-process FSM (textbook Mealy machine)
// No bugs expected.

module clean_fsm (
    input  wire clk,
    input  wire rst_n,
    input  wire req,
    input  wire ack,
    output reg  [1:0] state,
    output wire busy
);

localparam IDLE  = 2'b00;
localparam FETCH = 2'b01;
localparam EXEC  = 2'b10;
localparam DONE  = 2'b11;

// Process 1: state register with reset
always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n)
        state <= IDLE;
    else
        state <= next_state;
end

// Process 2: next-state logic (purely combinational, no latch)
reg [1:0] next_state;
always_comb begin
    case (state)
        IDLE:  next_state = req  ? FETCH : IDLE;
        FETCH: next_state = EXEC;
        EXEC:  next_state = ack  ? DONE  : EXEC;
        DONE:  next_state = IDLE;
        default: next_state = IDLE;   // safe default
    endcase
end

// Process 3: output logic
assign busy = (state != IDLE);

endmodule
