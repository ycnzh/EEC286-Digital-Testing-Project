`timescale 1ns/1ps

module tb;
  reg a, b, c;
  wire y;

  dut uut(.a(a), .b(b), .c(c), .y(y));

  integer fd, r;
  reg [255:0] line;
  reg [2:0] vec;

  initial begin
    fd = $fopen("vectors/test_vectors.txt", "r");
    if (fd == 0) begin
      $display("ERROR: cannot open vectors/test_vectors.txt");
      $finish;
    end

    while (!$feof(fd)) begin
      r = $fgets(line, fd);
      if (r != 0) begin
        r = $sscanf(line, "%b", vec);
        if (r == 1) begin
          {a,b,c} = vec;
          #1;
          $display("%b -> %b", vec, y);
        end
      end
    end

    $fclose(fd);
    $finish;
  end
endmodule
