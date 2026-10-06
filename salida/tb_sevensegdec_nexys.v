module tb_sevensegdec_nexys;

reg [3:0] bcd;
wire [6:0] sseg;
wire [3:0] bcdled;
wire [7:0] ssanodes;
reg invert;

initial begin
    $from_myhdl(
        bcd,
        invert
    );
    $to_myhdl(
        sseg,
        bcdled,
        ssanodes
    );
end

sevensegdec_nexys dut(
    bcd,
    sseg,
    bcdled,
    ssanodes,
    invert
);

endmodule
