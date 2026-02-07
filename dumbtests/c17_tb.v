`timescale 1ns/1ps

module c17_tb;

    // 1. 声明信号
    // inputs 对应 c17 的输入，类型为 reg (因为我们在 testbench 里给它赋值)
    reg N1, N2, N3, N6, N7;
    // outputs 对应 c17 的输出，类型为 wire
    wire N22, N23;

    // 2. 实例化待测模块 (Unit Under Test - UUT)
    // 这里的名字 c17 必须和你下载的 c17.v 里的 module 名字一致
    c17 uut (
        .N1(N1), .N2(N2), .N3(N3), .N6(N6), .N7(N7), 
        .N22(N22), .N23(N23)
    );

    // 3. 激励生成 (Stimulus)
    initial begin
        // 打开波形文件 (可选，用于调试)
        $dumpfile("c17_waveform.vcd");
        $dumpvars(0, c17_tb);

        // 打印表头
        $display("Time | Inputs (1,2,3,6,7) | Outputs (22,23)");
        $display("-------------------------------------------");

        // 测试向量 1
        N1=0; N2=0; N3=0; N6=0; N7=0;
        #10; // 等待 10ns
        $display("%4t | %b %b %b %b %b      | %b %b", $time, N1, N2, N3, N6, N7, N22, N23);

        // 测试向量 2 (随机变几个数)
        N1=1; N2=0; N3=1; N6=0; N7=1;
        #10;
        $display("%4t | %b %b %b %b %b      | %b %b", $time, N1, N2, N3, N6, N7, N22, N23);

        // 结束仿真
        $finish;
    end

endmodule