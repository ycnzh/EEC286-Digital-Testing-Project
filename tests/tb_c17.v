// Simple exhaustive testbench for c17
`timescale 1ns/1ps

module tb_c17;
  reg N1, N2, N3, N6, N7;
  wire N22, N23;
  integer i;

  c17 dut (
    .N1(N1),
    .N2(N2),
    .N3(N3),
    .N6(N6),
    .N7(N7),
    .N22(N22),
    .N23(N23)
  );

  initial begin
    $display("N1 N2 N3 N6 N7 | N22 N23");
    for (i = 0; i < 32; i = i + 1) begin
      {N1, N2, N3, N6, N7} = i[4:0];
      #1;
      $display("%0d  %0d  %0d  %0d  %0d  |  %0d   %0d",
               N1, N2, N3, N6, N7, N22, N23);
    end
    $finish;
  end
endmodule
