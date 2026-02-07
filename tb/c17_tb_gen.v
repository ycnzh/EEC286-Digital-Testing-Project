`timescale 1ns/1ps
module automated_tb;

  reg N1, N2, N3, N6, N7;
  wire N22, N23;
  reg [1:0] golden_out;
  integer detected_count = 0;
  integer total_faults_injected = 0;

  c17 uut (.N1(N1), .N2(N2), .N3(N3), .N6(N6), .N7(N7), .N22(N22), .N23(N23));

  initial begin
    $display("Input Order: N1,N2,N3,N6,N7");
    $display("-------------------------------------");


    // === Vector 0 ===
    N1=1; N2=1; N3=0; N6=1; N7=1;
    #10;
    golden_out = {N22, N23};
    total_faults_injected = total_faults_injected + 1;
    force uut.N10 = 1'b0;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N10 SA0 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N10;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N10 = 1'b1;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N10 SA1 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N10;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N11 = 1'b0;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N11 SA0 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N11;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N11 = 1'b1;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N11 SA1 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N11;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N16 = 1'b0;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N16 SA0 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N16;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N16 = 1'b1;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N16 SA1 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N16;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N19 = 1'b0;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N19 SA0 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N19;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N19 = 1'b1;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N19 SA1 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N19;
    #5;

    // === Vector 1 ===
    N1=1; N2=0; N3=0; N6=0; N7=0;
    #10;
    golden_out = {N22, N23};
    total_faults_injected = total_faults_injected + 1;
    force uut.N10 = 1'b0;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N10 SA0 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N10;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N10 = 1'b1;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N10 SA1 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N10;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N11 = 1'b0;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N11 SA0 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N11;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N11 = 1'b1;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N11 SA1 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N11;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N16 = 1'b0;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N16 SA0 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N16;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N16 = 1'b1;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N16 SA1 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N16;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N19 = 1'b0;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N19 SA0 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N19;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N19 = 1'b1;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N19 SA1 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N19;
    #5;

    // === Vector 2 ===
    N1=0; N2=0; N3=0; N6=1; N7=1;
    #10;
    golden_out = {N22, N23};
    total_faults_injected = total_faults_injected + 1;
    force uut.N10 = 1'b0;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N10 SA0 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N10;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N10 = 1'b1;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N10 SA1 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N10;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N11 = 1'b0;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N11 SA0 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N11;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N11 = 1'b1;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N11 SA1 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N11;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N16 = 1'b0;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N16 SA0 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N16;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N16 = 1'b1;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N16 SA1 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N16;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N19 = 1'b0;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N19 SA0 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N19;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N19 = 1'b1;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N19 SA1 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N19;
    #5;

    // === Vector 3 ===
    N1=1; N2=0; N3=0; N6=0; N7=1;
    #10;
    golden_out = {N22, N23};
    total_faults_injected = total_faults_injected + 1;
    force uut.N10 = 1'b0;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N10 SA0 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N10;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N10 = 1'b1;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N10 SA1 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N10;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N11 = 1'b0;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N11 SA0 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N11;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N11 = 1'b1;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N11 SA1 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N11;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N16 = 1'b0;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N16 SA0 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N16;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N16 = 1'b1;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N16 SA1 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N16;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N19 = 1'b0;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N19 SA0 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N19;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N19 = 1'b1;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N19 SA1 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N19;
    #5;

    // === Vector 4 ===
    N1=1; N2=1; N3=1; N6=1; N7=1;
    #10;
    golden_out = {N22, N23};
    total_faults_injected = total_faults_injected + 1;
    force uut.N10 = 1'b0;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N10 SA0 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N10;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N10 = 1'b1;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N10 SA1 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N10;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N11 = 1'b0;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N11 SA0 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N11;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N11 = 1'b1;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N11 SA1 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N11;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N16 = 1'b0;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N16 SA0 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N16;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N16 = 1'b1;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N16 SA1 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N16;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N19 = 1'b0;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N19 SA0 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N19;
    #5;
    total_faults_injected = total_faults_injected + 1;
    force uut.N19 = 1'b1;
    #10;
    if ({N22, N23} !== golden_out) begin
      $display("DETECTED: Input=%b | Fault: N19 SA1 | Golden:%b Faulty:%b", {N1, N2, N3, N6, N7}, golden_out, {N22, N23});
      detected_count = detected_count + 1;
    end
    release uut.N19;
    #5;

    $display("-------------------------------------");
    $display("Summary: Vectors=%0d, Total Injections=%0d, Detected=%0d", 
             5, total_faults_injected, detected_count);
    $finish;
  end
endmodule
