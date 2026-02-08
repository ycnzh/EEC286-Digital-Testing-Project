from __future__ import annotations

import csv
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .verilog_parse import parse_module_ports

## ----------------------------
# Parsing fault list
# ----------------------------

@dataclass(frozen=True)
class Fault:
    net: str          # hierarchical net name relative to uut (e.g., N10, N1@1, N1/1, etc.)
    sa: int           # 0 or 1
    raw: str = ""     # original line for traceability


def _parse_fault_line(line: str) -> Optional[Fault]:
    """
    Accept many formats:
      N10 SA0
      N10 sa1
      N10 stuck-at-0
      N10/0
      N10/1
      N10 s-a-0
    Also tolerates extra columns; we take first two tokens when possible.
    """
    s = line.strip()
    if not s or s.startswith("#") or s.startswith("//"):
        return None

    # normalize separators
    s = s.replace("\t", " ").strip()
    toks = [t for t in re.split(r"\s+", s) if t]

    # format: net/0 or net/1
    m = re.match(r"^(.+)[/](0|1)$", toks[0])
    if m:
        return Fault(net=m.group(1).strip(), sa=int(m.group(2)), raw=line.rstrip())

    if len(toks) >= 2:
        net = toks[0].strip()
        tag = toks[1].strip().lower()

        if tag in ("0", "1"):
            return Fault(net=net, sa=int(tag), raw=line.rstrip())

        # SA0 / SA1
        m2 = re.match(r"^(sa|s-a|stuck|stuck-at|sat|s@)\s*[-_]?(0|1)$", tag)
        if m2:
            return Fault(net=net, sa=int(m2.group(2)), raw=line.rstrip())

        # "stuck-at-0" style
        m3 = re.match(r"^stuck-at[-_]?([01])$", tag)
        if m3:
            return Fault(net=net, sa=int(m3.group(1)), raw=line.rstrip())

        # if second token contains 0/1 somewhere (best-effort)
        m4 = re.search(r"([01])$", tag)
        if m4 and ("sa" in tag or "stuck" in tag):
            return Fault(net=net, sa=int(m4.group(1)), raw=line.rstrip())

    # last resort: search ".../0" or ".../1" anywhere
    m5 = re.match(r"^(.+?)[\s,/]+(0|1)$", s)
    if m5:
        return Fault(net=m5.group(1).strip(), sa=int(m5.group(2)), raw=line.rstrip())

    return None


def load_faults(fault_file: str) -> List[Fault]:
    lines = Path(fault_file).read_text(encoding="utf-8", errors="ignore").splitlines()
    faults: List[Fault] = []
    for ln in lines:
        f = _parse_fault_line(ln)
        if f is not None:
            faults.append(f)
    # de-dup
    uniq: Dict[Tuple[str, int], Fault] = {}
    for f in faults:
        uniq[(f.net, f.sa)] = f
    return list(uniq.values())


# ----------------------------
# Verilog escaped identifiers
# ----------------------------

_IDENT_OK = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")

def _verilog_ref(uut_inst: str, net: str) -> str:
    # Return hierarchical reference "uut.net".
    # If net contains special chars, use Verilog escaped identifier: uut.\<net><space>
    # IMPORTANT: do NOT write "\N" in any Python string literal anywhere (unicode escape).
    if _IDENT_OK.match(net):
        return f"{uut_inst}.{net}"
    return f"{uut_inst}." + ("\\" + net + " ")


# ----------------------------
# TB generation + simulation
# ----------------------------

def _ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)

def _write_text(path: str, content: str) -> None:
    Path(path).write_text(content, encoding="utf-8")


def generate_tb(
    tb_path: str,
    module_name: str,
    uut_inst: str,
    inputs: List[str],
    outputs: List[str],
    vectors: List[Dict[str, int]],
    faults: List[Fault],
) -> None:
    """
    Simple golden-then-faulty comparison:
      - apply vector
      - wait
      - capture golden outputs
      - for each fault: force net, wait, compare, release
    """
    _ensure_dir(str(Path(tb_path).parent))

    # Build concatenations (keep stable order)
    concat_in = "{" + ", ".join(inputs) + "}"
    concat_out = "{" + ", ".join(outputs) + "}"
    out_w = max(len(outputs), 1)

    lines: List[str] = []
    lines.append("`timescale 1ns/1ps")
    lines.append("module automated_tb;")
    lines.append("")

    # regs/wires
    lines.append("  // Inputs")
    for nm in inputs:
        lines.append(f"  reg {nm};")
    lines.append("")
    lines.append("  // Outputs")
    for nm in outputs:
        lines.append(f"  wire {nm};")
    lines.append("")

    lines.append(f"  reg [{out_w-1}:0] golden_out;")
    lines.append("  integer detected = 0;")
    lines.append("  integer injected = 0;")
    lines.append("")

    # instantiate UUT
    port_map = [f".{p}({p})" for p in inputs + outputs]
    lines.append(f"  {module_name} {uut_inst} ({', '.join(port_map)});")
    lines.append("")

    lines.append("  initial begin")
    lines.append(f'    $display("InputOrder: {",".join(inputs)}");')
    lines.append(f'    $display("OutputOrder: {",".join(outputs)}");')
    lines.append('    $display("-------------------------------------");')

    # vectors loop
    for i, vec in enumerate(vectors):
        lines.append("")
        lines.append(f"    // ===== Vector {i} =====")
        for nm in inputs:
            v = int(vec[nm])
            lines.append(f"    {nm} = 1'b{v};")
        lines.append("    #5;")
        lines.append(f"    golden_out = {concat_out};")
        lines.append("    #1;")

        # faults loop
        for f in faults:
            ref = _verilog_ref(uut_inst, f.net)
            lines.append(f"    injected = injected + 1;")
            lines.append(f"    force {ref} = 1'b{f.sa};")
            lines.append("    #5;")
            lines.append(f"    if ({concat_out} !== golden_out) begin")
            lines.append(
                f'      $display("DETECTED vec={i} in=%b fault={f.net} sa={f.sa} golden=%b faulty=%b", '
                f"{concat_in}, golden_out, {concat_out});"
            )
            lines.append("      detected = detected + 1;")
            lines.append("    end")
            lines.append(f"    release {ref};")
            lines.append("    #1;")

    lines.append("")
    lines.append('    $display("-------------------------------------");')
    lines.append('    $display("SUMMARY: vectors=%0d faults=%0d injected=%0d detected=%0d", '
                 f"{len(vectors)}, {len(faults)}, injected, detected);")
    lines.append("    $finish;")
    lines.append("  end")
    lines.append("endmodule")

    _write_text(tb_path, "\n".join(lines) + "\n")


def run_iverilog(
    tb_path: str,
    verilog_path: str,
    sim_exe: str,
) -> str:
    """
    Compile + run, return stdout.
    """
    # compile
    subprocess.check_call(["iverilog", "-o", sim_exe, tb_path, verilog_path])
    # run
    r = subprocess.run(["vvp", sim_exe], capture_output=True, text=True, check=False)
    return r.stdout


def parse_summary(stdout: str) -> Tuple[int, int, int, int]:
    """
    Parse:
      SUMMARY: vectors=... faults=... injected=... detected=...
    """
    vec = faults = injected = detected = 0
    for ln in stdout.splitlines():
        m = re.search(
            r"SUMMARY:\s*vectors=(\d+)\s*faults=(\d+)\s*injected=(\d+)\s*detected=(\d+)", ln
        )
        if m:
            vec, faults, injected, detected = map(int, m.groups())
            break
    return vec, faults, injected, detected


def make_random_vectors(inputs: List[str], n: int, seed: int) -> List[Dict[str, int]]:
    rnd = __import__("random")
    rnd.seed(seed)
    vecs: List[Dict[str, int]] = []
    for _ in range(n):
        vecs.append({nm: rnd.randint(0, 1) for nm in inputs})
    return vecs


def default_faults_from_verilog(verilog_path: str) -> List[Fault]:
    """
    If no expanded fault list is provided, we do a reasonable baseline:
      - Parse wire declarations and inputs as candidate nets
      - Create SA0/SA1 for each
    This is NOT the "theoretical full" list (fanout branches etc.),
    but is good for sanity and early testing.
    """
    txt = Path(verilog_path).read_text(encoding="utf-8", errors="ignore")
    txt = re.sub(r"/\*.*?\*/", "", txt, flags=re.S)
    txt = re.sub(r"//.*?$", "", txt, flags=re.M)

    # collect wire names (very common in ISCAS netlists)
    wires: List[str] = []
    for m in re.finditer(r"\bwire\b\s*([^;]+);", txt, flags=re.I | re.M):
        blob = m.group(1).replace("\n", " ")
        parts = [p.strip() for p in blob.split(",") if p.strip()]
        wires.extend(parts)

    mi = parse_module_ports(verilog_path)
    nets = sorted(set([p.name for p in mi.inputs] + wires))
    faults: List[Fault] = []
    for n in nets:
        faults.append(Fault(net=n, sa=0, raw=f"{n} SA0"))
        faults.append(Fault(net=n, sa=1, raw=f"{n} SA1"))
    return faults


def run_coverage_once(
    circuit: str,
    verilog_path: str,
    tb_dir: str,
    vectors_n: int,
    seed: int,
    fault_file: Optional[str] = None,
    csv_path: Optional[str] = None,
) -> Dict[str, object]:
    """
    Main API used by run_coverage.py
    """
    mi = parse_module_ports(verilog_path)
    inputs = [p.name for p in mi.inputs]
    outputs = [p.name for p in mi.outputs]

    vecs = make_random_vectors(inputs, vectors_n, seed)

    if fault_file:
        faults = load_faults(fault_file)
    else:
        faults = default_faults_from_verilog(verilog_path)

    tb_path = str(Path(tb_dir) / f"{circuit}_tb_gen.v")
    sim_exe = str(Path(tb_dir) / f"{circuit}_sim")

    generate_tb(
        tb_path=tb_path,
        module_name=mi.name,
        uut_inst="uut",
        inputs=inputs,
        outputs=outputs,
        vectors=vecs,
        faults=faults,
    )

    out = run_iverilog(tb_path, verilog_path, sim_exe)
    vec_cnt, fault_cnt, injected, detected = parse_summary(out)

    # Coverage definition (fault-level): detected_faults / total_faults
    # Note: our TB counts detection events, not unique faults. We approximate unique-detected by parsing DETECTED lines.
    detected_set = set()
    for ln in out.splitlines():
        if ln.startswith("DETECTED"):
            # contains: fault=<net> sa=<0/1>
            m = re.search(r"fault=([^\s]+)\s+sa=([01])", ln)
            if m:
                detected_set.add((m.group(1), int(m.group(2))))
    unique_detected = len(detected_set)
    coverage = (unique_detected / fault_cnt) if fault_cnt > 0 else 0.0

    result = {
        "circuit": circuit,
        "module": mi.name,
        "vectors": vec_cnt,
        "faults": fault_cnt,
        "unique_detected": unique_detected,
        "coverage": coverage,
        "seed": seed,
        "fault_file": fault_file or "",
        "tb": tb_path,
    }

    if csv_path:
        Path(csv_path).parent.mkdir(parents=True, exist_ok=True)
        write_header = not Path(csv_path).exists()
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "circuit",
                    "module",
                    "vectors",
                    "faults",
                    "unique_detected",
                    "coverage",
                    "seed",
                    "fault_file",
                    "tb",
                ],
            )
            if write_header:
                w.writeheader()
            w.writerow(result)

    return result
