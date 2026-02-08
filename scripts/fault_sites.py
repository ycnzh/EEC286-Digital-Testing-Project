import re
import sys
from pathlib import Path
from collections import defaultdict


BASE_DIR = Path(__file__).resolve().parent.parent
VERILOG_DIR = BASE_DIR / "circuits" / "verilog"
OUT_DIR = BASE_DIR / "experiment_results"
OUT_DIR.mkdir(exist_ok=True)


def split_list(s):
    return [x.strip() for x in s.replace("\n"," ").split(",") if x.strip()]


def parse_verilog(vfile):
    txt = open(vfile).read()

    inputs = sum(
        [split_list(x) for x in re.findall(r"input\s+([^;]+);", txt)],
        []
    )

    gates = []
    for gtype,name,plist in re.findall(
        r"\b(and|or|nand|nor|xor|xnor|not|buf)\b\s+(\w+)\s*\(([^;]+)\);",
        txt, re.I):

        ports = split_list(plist)
        if len(ports) >= 1:
            gates.append((name, ports[0], ports[1:]))

    return inputs, gates


def compute_fault_sites(vfile):

    PI, gates = parse_verilog(vfile)

    fanout = defaultdict(list)
    for gname,out,ins in gates:
        for net in ins:
            fanout[net].append(gname)

    sites = []

    for pi in PI:
        sites.append(("STEM", pi))

    for gname,out,_ in gates:
        sites.append(("STEM", out))

    for net, users in fanout.items():
        if len(users) > 1:
            for g in users:
                sites.append(("BRANCH", f"{net}->{g}"))

    return sites


# ----------------------
# run one circuit
# ----------------------
def run_one(name):

    vfile = VERILOG_DIR / f"{name}.v"
    if not vfile.exists():
        print(f"❌ skip (not found): {name}")
        return

    sites = compute_fault_sites(vfile)

    faults = []
    for t, s in sites:
        faults.append(f"{t}:{s} SA0")
        faults.append(f"{t}:{s} SA1")

    # ---- print summary only ----
    print(f"{name:6s}  sites={len(sites):4d}  full_faults={len(faults):4d}")

    # ---- write report ----
    out_file = OUT_DIR / f"fault_report_{name}.txt"
    with open(out_file, "w") as f:
        f.write(f"Circuit: {name}\n\n")
        for line in faults:
            f.write(line + "\n")
        f.write("\nSUMMARY\n")
        f.write(f"Fault sites    : {len(sites)}\n")
        f.write(f"Full SA faults : {len(faults)}\n")


# ----------------------
# main
# ----------------------
def main():

    if len(sys.argv) != 2:
        print("usage: python fault_sites.py <circuit|all>")
        sys.exit(1)

    arg = sys.argv[1]

    if arg == "all":
        print("\n=== Batch fault-site analysis ===\n")
        for vfile in sorted(VERILOG_DIR.glob("*.v")):
            run_one(vfile.stem)

        print("\nReports written to experiment_results/\n")
        return

    run_one(arg)


if __name__ == "__main__":
    main()
