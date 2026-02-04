import os
import subprocess

DUT = "bench/dut.v"
TB  = "tb/tb.v"
VEC = "vectors/test_vectors.txt"

MUT_DIR = "mutants"
OUT_DIR = "outputs"

NODES = ["a", "b", "c", "y"]

def make_faulty(node, sa):
    fname = f"{MUT_DIR}/dut_{node}_sa{sa}.v"
    with open(fname, "w") as f:
        f.write(f"""module dut(
  input  wire a,
  input  wire b,
  input  wire c,
  output wire y
);
  assign {node} = 1'b{sa};
endmodule
""")
    return fname

def run_sim(verilog, tag):
    out_bin = f"{OUT_DIR}/{tag}.out"
    out_txt = f"{OUT_DIR}/{tag}.txt"

    subprocess.run(["iverilog", "-o", out_bin, TB, verilog], check=True)
    with open(out_txt, "w") as f:
        subprocess.run(["vvp", out_bin], stdout=f, check=True)

    return out_txt

def detected(golden, faulty):
    with open(golden) as fg, open(faulty) as ff:
        for g, f in zip(fg, ff):
            if g.strip() != f.strip():
                return True
    return False

def main():
    golden = f"{OUT_DIR}/golden_output.txt"
    total = 0
    hit   = 0

    os.makedirs(MUT_DIR, exist_ok=True)

    for n in NODES:
        for sa in [0,1]:
            total += 1
            vf = make_faulty(n, sa)
            tag = f"{n}_sa{sa}"
            fout = run_sim(vf, tag)

            if detected(golden, fout):
                hit += 1
                print(f"[DETECTED] {tag}")
            else:
                print(f"[NOT DETECTED] {tag}")

    print(f"Coverage = {hit}/{total} = {hit/total:.2f}")

if __name__ == "__main__":
    main()
