import subprocess
import random
import os
import re

# ===========================
# 1. 路径与配置 (Path Setup)
# ===========================
# 获取当前脚本所在目录 (scripts/)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# 获取项目根目录 (EEC286-Digital-Testing-Project/)
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)

# 定义路径
VERILOG_DIR = os.path.join(PROJECT_ROOT, "circuits", "verilog")
# 新增: TB 目录 (存放生成的 testbench 和仿真文件)
TB_DIR = os.path.join(PROJECT_ROOT, "tb")

# 确保 tb 目录存在，如果不存在则创建
os.makedirs(TB_DIR, exist_ok=True)

# 目标电路名称
CIRCUIT_NAME = "c17" 

# 文件路径配置
SOURCE_VERILOG = os.path.join(VERILOG_DIR, f"{CIRCUIT_NAME}.v")
# 修改: 将生成的 Testbench 放到 tb/ 目录下
TB_FILENAME = os.path.join(TB_DIR, f"{CIRCUIT_NAME}_tb_gen.v")
# 修改: 将仿真可执行文件也放到 tb/ 目录下，避免污染 scripts
SIM_EXE = os.path.join(TB_DIR, f"{CIRCUIT_NAME}_sim")

# ===========================
# 2. Verilog 解析器 (Parser)
# ===========================
def parse_verilog_info(file_path):
    """
    解析 ISCAS85 Verilog 文件，提取 input, output, wire。
    """
    inputs = []
    outputs = []
    wires = []

    print(f"[Parser] Reading {file_path}...")
    
    with open(file_path, 'r') as f:
        content = f.read()
        
        # 移除注释
        content = re.sub(r'//.*', '', content)
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)

        # 提取 input
        input_match = re.search(r'input\s+([^;]+);', content, re.DOTALL)
        if input_match:
            raw_txt = input_match.group(1).replace('\n', '')
            inputs = [x.strip() for x in raw_txt.split(',') if x.strip()]

        # 提取 output
        output_match = re.search(r'output\s+([^;]+);', content, re.DOTALL)
        if output_match:
            raw_txt = output_match.group(1).replace('\n', '')
            outputs = [x.strip() for x in raw_txt.split(',') if x.strip()]

        # 提取 wire
        wire_match = re.search(r'wire\s+([^;]+);', content, re.DOTALL)
        if wire_match:
            raw_txt = wire_match.group(1).replace('\n', '')
            wires = [x.strip() for x in raw_txt.split(',') if x.strip()]

    print(f"[Parser] Found {len(inputs)} Inputs, {len(outputs)} Outputs, {len(wires)} Internal Wires.")
    return inputs, outputs, wires

# ===========================
# 3. Testbench 生成器
# ===========================
def generate_testbench(inputs, outputs, fault_candidates, vector_count=5):
    """
    生成包含 Random Pattern + Fault Injection 的 Testbench
    """
    print(f"[Generator] Creating testbench at: {TB_FILENAME}")
    
    with open(TB_FILENAME, "w") as f:
        f.write(f"`timescale 1ns/1ps\n")
        f.write(f"module automated_tb;\n\n")
        
        # 定义信号
        f.write(f"  reg {', '.join(inputs)};\n")
        f.write(f"  wire {', '.join(outputs)};\n")
        
        # 定义变量
        f.write(f"  reg [{len(outputs)-1}:0] golden_out;\n")
        f.write(f"  integer detected_count = 0;\n")
        f.write(f"  integer total_faults_injected = 0;\n\n")

        # 实例化 UUT
        ports = [f".{p}({p})" for p in inputs + outputs]
        f.write(f"  {CIRCUIT_NAME} uut ({', '.join(ports)});\n\n")
        
        f.write("  initial begin\n")
        
        # 准备拼接字符串，用于 Display
        # inputs: {N1, N2, N3...}
        concat_inputs = "{" + ", ".join(inputs) + "}"
        # outputs: {N22, N23...}
        concat_outputs = "{" + ", ".join(outputs) + "}"
        
        # 打印 Input 的顺序，方便用户对照
        input_names_str = ",".join(inputs)
        f.write(f'    $display("Input Order: {input_names_str}");\n')
        f.write('    $display("-------------------------------------");\n\n')

        # --- 循环：测试向量 ---
        for i in range(vector_count):
            # 生成随机输入
            input_vals = {inp: random.randint(0, 1) for inp in inputs}
            assign_str = " ".join([f"{k}={v};" for k,v in input_vals.items()])
            
            f.write(f"\n    // === Vector {i} ===\n")
            f.write(f"    {assign_str}\n")
            f.write("    #10;\n") 
            
            # 1. 获取 Golden Output
            f.write(f"    golden_out = {concat_outputs};\n")
            
            # 2. 注入故障
            for wire in fault_candidates:
                for sa_val in [0, 1]:
                    type_str = "SA0" if sa_val == 0 else "SA1"
                    
                    f.write(f"    total_faults_injected = total_faults_injected + 1;\n")
                    
                    # Force
                    f.write(f"    force uut.{wire} = 1'b{sa_val};\n")
                    f.write("    #10;\n")
                    
                    # Compare
                    # 修改点：在 $display 中加入 concat_inputs 来显示当前输入值
                    f.write(f"    if ({concat_outputs} !== golden_out) begin\n")
                    f.write(f'      $display("DETECTED: Input=%b | Fault: {wire} {type_str} | Golden:%b Faulty:%b", {concat_inputs}, golden_out, {concat_outputs});\n')
                    f.write(f"      detected_count = detected_count + 1;\n")
                    f.write(f"    end\n")
                    
                    # Release
                    f.write(f"    release uut.{wire};\n")
                    f.write("    #5;\n")

        f.write('\n    $display("-------------------------------------");\n')
        f.write('    $display("Summary: Vectors=%0d, Total Injections=%0d, Detected=%0d", \n')
        f.write(f'             {vector_count}, total_faults_injected, detected_count);\n')
        f.write("    $finish;\n")
        f.write("  end\n")
        f.write("endmodule\n")

# ===========================
# 4. 主程序
# ===========================
def run_simulation():
    if not os.path.exists(SOURCE_VERILOG):
        print(f"Error: Verilog file not found at {SOURCE_VERILOG}")
        return

    # 1. 解析
    inputs, outputs, wires = parse_verilog_info(SOURCE_VERILOG)
    fault_candidates = wires if wires else inputs
    
    # 2. 生成 Testbench (到 tb/ 目录)
    generate_testbench(inputs, outputs, fault_candidates, vector_count=5)
    
    # 3. 编译 (Output 到 tb/ 目录)
    print(f"[Simulator] Compiling to {SIM_EXE}...")
    compile_cmd = ["iverilog", "-o", SIM_EXE, TB_FILENAME, SOURCE_VERILOG]
    subprocess.check_call(compile_cmd)
    
    # 4. 运行
    print("[Simulator] Running...")
    run_cmd = ["vvp", SIM_EXE]
    result = subprocess.run(run_cmd, capture_output=True, text=True)
    
    # 5. 显示结果
    print("\n=== Simulation Results ===")
    # 打印 Input Order 这一行，方便查阅
    for line in result.stdout.splitlines():
        if "Input Order" in line:
            print(line)
        if "DETECTED" in line or "Summary" in line:
            print(line)

if __name__ == "__main__":
    run_simulation()