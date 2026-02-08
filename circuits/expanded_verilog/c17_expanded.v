module c17_expanded (N1, N2, N3, N6, N7, N22, N23);

  // Standard Definitions
  input N1, N2, N3, N6, N7;
  output N22, N23;
  wire N10, N11, N16, N19;

  // Isolated Branch Wires (Fanout > 1)
  wire K1, K2, K3, K4, K5, K6;

  // Fanout Decoupling Assignments
  assign K1 = N3;
  assign K2 = N3;
  assign K3 = N11;
  assign K4 = N11;
  assign K5 = N16;
  assign K6 = N16;

  // Gate Instantiations
  nand NAND2_1 (N10, N1, K1);
  nand NAND2_2 (N11, K2, N6);
  nand NAND2_3 (N16, N2, K3);
  nand NAND2_4 (N19, K4, N7);
  nand NAND2_5 (N22, N10, K5);
  nand NAND2_6 (N23, K6, N19);

endmodule