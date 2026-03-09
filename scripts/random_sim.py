#!/usr/bin/env python3
"""
Purely Random ISCAS Fault Simulator (with CSV Data Logging)
================================================================
- Generates fully random test vectors using a fixed seed.
- Logs per-vector coverage data to a CSV file for MATLAB plotting.
- Stops if:
  1. Coverage reaches 95%
  2. Runtime exceeds 30 minutes
  3. Coverage improves by less than 0.1% over a batch of 100 vectors
"""

import sys
import re
import random
import os
import time

# ============================================================
#  CONFIGURATION
# ============================================================
TIMEOUT_SECONDS = 18000    # 300 minutes
TARGET_COVERAGE = 97.0
MIN_IMPROVEMENT = 0.1      # 0.1% improvement required...
BATCH_SIZE = 100           # ...over a batch of 100 vectors

# ============================================================
#  1.  PARSERS 
# ============================================================
def parse_expanded_verilog(filepath):
    with open(filepath) as f:
        content = f.read()

    m = re.search(r'\binput\b(.*?);', content, re.DOTALL)
    inputs = re.findall(r'\b[A-Z]\w*\b', m.group(1)) if m else []

    m = re.search(r'\boutput\b(.*?);', content, re.DOTALL)
    outputs = re.findall(r'\b[A-Z]\w*\b', m.group(1)) if m else []

    k_assign = {}
    for m in re.finditer(r'assign\s+(K\d+)\s*=\s*(\w+)\s*;', content):
        k_assign[m.group(1)] = m.group(2)

    gates = []
    gate_pat = re.compile(
        r'\b(not|buf|nand|nor|and|or|xor|xnor)\b\s+'
        r'(\w+)\s*\('
        r'(.*?)\)\s*;',
        re.DOTALL | re.IGNORECASE
    )
    for m in gate_pat.finditer(content):
        ports = [p.strip() for p in m.group(3).split(',')]
        gates.append({
            'type':   m.group(1).lower(),
            'name':   m.group(2),
            'output': ports[0],
            'inputs': ports[1:],
        })

    return inputs, outputs, k_assign, gates

def parse_fault_report(filepath):
    faults = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            m = re.match(r'STEM:(\w+)\s+SA([01])', line)
            if m:
                faults.append(('STEM', m.group(1), None, int(m.group(2))))
                continue
            m = re.match(r'BRANCH:(\w+)->(\w+)\s+SA([01])', line)
            if m:
                faults.append(('BRANCH', m.group(1), m.group(2), int(m.group(3))))
    return faults

# ============================================================
#  2.  CIRCUIT EVALUATOR
# ============================================================
def evaluate(gates, k_assign, input_names, input_vals, fault=None):
    net = dict(zip(input_names, input_vals))

    if fault and fault[0] == 'STEM' and fault[1] in net:
        net[fault[1]] = fault[3]

    def get(node, gate_name):
        if node.startswith('K'):
            stem = k_assign.get(node, node)
            val  = net.get(stem, 0)
            if (fault and fault[0] == 'BRANCH'
                    and fault[1] == stem and fault[2] == gate_name):
                val = fault[3]
        else:
            val = net.get(node, 0)
            if (fault and fault[0] == 'BRANCH'
                    and fault[1] == node and fault[2] == gate_name):
                val = fault[3]
        return val

    for g in gates:
        gtype, gname, out = g['type'], g['name'], g['output']
        iv = [get(inp, gname) for inp in g['inputs']]

        if   gtype == 'not':   val = 1 - iv[0]
        elif gtype == 'buf':   val = iv[0]
        elif gtype == 'nand':  val = 0 if all(v == 1 for v in iv) else 1
        elif gtype == 'nor':   val = 0 if any(v == 1 for v in iv) else 1
        elif gtype == 'and':   val = 1 if all(v == 1 for v in iv) else 0
        elif gtype == 'or':    val = 1 if any(v == 1 for v in iv) else 0
        elif gtype == 'xor':   val = iv[0] ^ iv[1]
        elif gtype == 'xnor':  val = 1 - (iv[0] ^ iv[1])
        else:                  val = 0

        if fault and fault[0] == 'STEM' and fault[1] == out:
            val = fault[3]

        net[out] = val

    return net

# ============================================================
#  3.  MAIN SIMULATION LOOP
# ============================================================
def run_random_sim(circuit_name):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    verilog_file = os.path.join(base_dir, 'circuits', 'expanded_verilog', f'{circuit_name}_expanded.v')
    fault_file   = os.path.join(base_dir, 'experiment_results', f'fault_report_{circuit_name}.txt')
    
    # Setup Data Logging Directory
    plot_dir = os.path.join(base_dir, 'coverage_results', 'plot_data')
    os.makedirs(plot_dir, exist_ok=True)
    csv_file = os.path.join(plot_dir, f'random_sim_{circuit_name}.csv')
    
    if not os.path.exists(verilog_file) or not os.path.exists(fault_file):
        print(f"Error: Missing files for {circuit_name}")
        return

    inputs, outputs, k_assign, gates = parse_expanded_verilog(verilog_file)
    faults = parse_fault_report(fault_file)

    n_in = len(inputs)
    n_faults = len(faults)
    remaining_set = set(range(n_faults))
    
    detected = 0
    vectors_generated = 0
    last_batch_coverage = 0.0
    
    random.seed(42)
    t_start = time.time()

    print("=" * 68)
    print(f"  PURELY RANDOM SIMULATION: {circuit_name}")
    print("=" * 68)
    print(f"  Inputs / Gates : {n_in} / {len(gates)}")
    print(f"  Total Faults   : {n_faults}")
    print(f"  Data Log       : {csv_file}")
    print("-" * 68)
    print(f"{'Time(s)':<10} | {'Vectors':<10} | {'Detected':<10} | {'Coverage':<10}")
    print("-" * 68)

    # Open CSV for writing
    with open(csv_file, 'w') as f_csv:
        # Write CSV Header
        f_csv.write("Vector_Index,Time_Seconds,Total_Detected,Delta_Detected,Coverage_Percent,Delta_Coverage\n")

        while True:
            elapsed_time = time.time() - t_start
            current_coverage = (detected / n_faults) * 100.0

            # Stop Condition 1: Time Limit
            if elapsed_time >= TIMEOUT_SECONDS:
                stop_reason = "30 Minute Time Limit Exceeded"
                break

            # Stop Condition 2: Coverage Target
            if current_coverage >= TARGET_COVERAGE:
                stop_reason = "95% Coverage Reached"
                break

            # Stop Condition 3: Diminishing Returns (checked every BATCH_SIZE vectors)
            if vectors_generated > 0 and vectors_generated % BATCH_SIZE == 0:
                improvement = current_coverage - last_batch_coverage
                if improvement < MIN_IMPROVEMENT:
                    stop_reason = f"Coverage plateaued (<{MIN_IMPROVEMENT}% improvement over {BATCH_SIZE} vectors)"
                    break
                last_batch_coverage = current_coverage

            # Generate strictly random vector
            vec = [random.choice([0, 1]) for _ in range(n_in)]
            vectors_generated += 1

            # Simulate Golden Model
            good_net = evaluate(gates, k_assign, inputs, vec, fault=None)
            good_out = tuple(good_net[o] for o in outputs)
            
            # Fault Simulation & Dropping
            newly_detected = []
            for fi in list(remaining_set):
                fn = evaluate(gates, k_assign, inputs, vec, fault=faults[fi])
                if tuple(fn[o] for o in outputs) != good_out:
                    newly_detected.append(fi)
                    
            # Calculate metrics for logging
            delta_detected = len(newly_detected)
            delta_coverage = (delta_detected / n_faults) * 100.0
            
            if newly_detected:
                for fi in newly_detected:
                    remaining_set.discard(fi)
                detected += delta_detected
                current_coverage = (detected / n_faults) * 100.0
                print(f"{elapsed_time:<10.1f} | {vectors_generated:<10} | {detected:<10} | {current_coverage:.2f}%")

            # Write row to CSV
            f_csv.write(f"{vectors_generated},{elapsed_time:.4f},{detected},{delta_detected},{current_coverage:.4f},{delta_coverage:.4f}\n")

    print("=" * 68)
    print("  FINAL RANDOM SIMULATION REPORT")
    print("=" * 68)
    print(f"  Stop Reason        : {stop_reason}")
    print(f"  Total Time         : {elapsed_time:.2f} seconds")
    print(f"  Vectors Generated  : {vectors_generated}")
    print(f"  Faults Detected    : {detected} / {n_faults}")
    print(f"  Final Coverage     : {current_coverage:.2f}%")
    print(f"  Plot Data Saved To : {csv_file}")
    print("=" * 68)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/random_sim.py <circuit_name>")
        sys.exit(1)
    run_random_sim(sys.argv[1])