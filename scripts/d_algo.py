#!/usr/bin/env python3
"""
ISCAS D-Algorithm ATPG Simulator (with CSV Data Logging)
================================================================
- Generates targeted test vectors using structural backtracing.
- Employs Union-Find equivalence fault collapsing.
- Logs per-vector coverage data to a CSV file for MATLAB plotting.
- Stops if:
  1. Coverage reaches 95%
  2. Runtime exceeds 30 minutes
  3. Coverage improves by less than 0.1% over a batch of 100 vectors
"""

import sys
import os
import time
import random
import re
from collections import defaultdict

# ============================================================
#  CONFIGURATION
# ============================================================
TIMEOUT_SECONDS = 18000     # 30 minutes
TARGET_COVERAGE = 90.0
MIN_IMPROVEMENT = 0.1      # 0.1% improvement required...
BATCH_SIZE = 100           # ...over a batch of 100 vectors for ATPG

# ==========================================
# 1. Netlist Parsing & Data Structures
# ==========================================
class Node:
    def __init__(self, name, node_type="wire"):
        self.name = name
        self.type = node_type 
        self.value = None     
        self.driven_by = None 
        self.drives = []      

class Circuit:
    def __init__(self):
        self.nodes = {}
        self.inputs = []
        self.outputs = []
        
    def get_node(self, name):
        if name not in self.nodes:
            self.nodes[name] = Node(name)
        return self.nodes[name]

def parse_expanded_netlist(filepath):
    circuit = Circuit()
    with open(filepath, 'r') as f:
        content = f.read()
        
    # Strip comments BEFORE removing newlines
    content = re.sub(r'//.*', ' ', content)
    content = re.sub(r'/\*.*?\*/', ' ', content, flags=re.DOTALL)
    
    content = content.replace('\n', ' ').replace('\r', ' ')
    statements = [s.strip() for s in content.split(';') if s.strip()]
    
    for stmt in statements:
        parts = stmt.split(' ', 1)
        keyword = parts[0]
        body = parts[1] if len(parts) > 1 else ""
        
        if keyword == 'input':
            for p in body.split(','):
                name = p.strip()
                circuit.get_node(name).type = "input"
                circuit.inputs.append(name)
        elif keyword == 'output':
            for p in body.split(','):
                name = p.strip()
                circuit.get_node(name).type = "output"
                circuit.outputs.append(name)
        elif keyword in ['and', 'nand', 'or', 'nor', 'xor', 'xnor', 'not', 'buf']:
            idx_open = body.find('(')
            idx_close = body.rfind(')')
            if idx_open != -1 and idx_close != -1:
                pins = [p.strip() for p in body[idx_open+1:idx_close].split(',')]
                out_pin = pins[0]
                in_pins = pins[1:]
                
                circuit.get_node(out_pin).driven_by = (keyword, in_pins)
                for in_p in in_pins:
                    circuit.get_node(in_p).drives.append(keyword)
        elif keyword == 'assign':
            match = body.split('=')
            if len(match) == 2:
                out_pin = match[0].strip()
                in_pin = match[1].strip()
                circuit.get_node(out_pin).driven_by = ('buf', [in_pin])
                circuit.get_node(in_pin).drives.append('buf')
                
    return circuit

def parse_fault_report(filepath):
    # Used solely to get the exact baseline fault count for accurate coverage %
    faults = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if re.match(r'STEM:(\w+)\s+SA([01])', line) or re.match(r'BRANCH:(\w+)->(\w+)\s+SA([01])', line):
                faults.append(line)
    return len(faults)

# ==========================================
# 2. Strict Equivalence Collapsing (Union-Find)
# ==========================================
def build_equivalence_classes(circuit):
    parent = {}
    
    # Initialize Disjoint Set
    for name in circuit.nodes:
        parent[(name, 0)] = (name, 0)
        parent[(name, 1)] = (name, 1)
        
    def find(i):
        if parent[i] == i: return i
        parent[i] = find(parent[i])
        return parent[i]

    def union(in_fault, out_fault):
        root_in = find(in_fault)
        root_out = find(out_fault)
        if root_in != root_out:
            parent[root_in] = root_out

    # Apply rules ONLY if input fanout is exactly 1
    for name, node in circuit.nodes.items():
        if not node.driven_by: continue
        
        g_type, ins = node.driven_by
        out_n = name
        
        if g_type == 'and':
            for inp in ins:
                if len(circuit.nodes[inp].drives) == 1: union((inp, 0), (out_n, 0))
        elif g_type == 'nand':
            for inp in ins:
                if len(circuit.nodes[inp].drives) == 1: union((inp, 0), (out_n, 1))
        elif g_type == 'or':
            for inp in ins:
                if len(circuit.nodes[inp].drives) == 1: union((inp, 1), (out_n, 1))
        elif g_type == 'nor':
            for inp in ins:
                if len(circuit.nodes[inp].drives) == 1: union((inp, 1), (out_n, 0))
        elif g_type == 'not':
            if len(circuit.nodes[ins[0]].drives) == 1:
                union((ins[0], 0), (out_n, 1))
                union((ins[0], 1), (out_n, 0))
        elif g_type == 'buf':
            if len(circuit.nodes[ins[0]].drives) == 1:
                union((ins[0], 0), (out_n, 0))
                union((ins[0], 1), (out_n, 1))

    # Build the final mapping
    equiv_map = defaultdict(list)
    for fault in parent.keys():
        root = find(fault)
        equiv_map[root].append(fault)
        
    return equiv_map, len(parent)

# ==========================================
# 3. Logic & Fault Simulator
# ==========================================
def evaluate_gate(g_type, in_vals):
    if None in in_vals: return None 
    if g_type == 'and': return 1 if all(v == 1 for v in in_vals) else 0
    if g_type == 'nand': return 0 if all(v == 1 for v in in_vals) else 1
    if g_type == 'or': return 1 if any(v == 1 for v in in_vals) else 0
    if g_type == 'nor': return 0 if any(v == 1 for v in in_vals) else 1
    if g_type == 'not': return 1 - in_vals[0]
    if g_type == 'buf': return in_vals[0]
    if g_type == 'xor': return in_vals[0] ^ in_vals[1]
    if g_type == 'xnor': return 1 - (in_vals[0] ^ in_vals[1])
    return None

def simulate(circuit, vector, fault=None):
    for node in circuit.nodes.values():
        node.value = None
        
    for pi, val in vector.items():
        if fault and pi == fault[0]:
            circuit.nodes[pi].value = fault[1]
        else:
            circuit.nodes[pi].value = val
            
    progress = True
    while progress:
        progress = False
        for name, node in circuit.nodes.items():
            if node.value is None and node.driven_by:
                g_type, ins = node.driven_by
                in_vals = [circuit.nodes[i].value for i in ins]
                
                if None not in in_vals:
                    if fault and name == fault[0]:
                        node.value = fault[1]
                    else:
                        node.value = evaluate_gate(g_type, in_vals)
                    progress = True
                    
    return tuple(circuit.nodes[po].value for po in circuit.outputs)

def compute_detected_roots(circuit, vector, active_roots):
    golden_outputs = simulate(circuit, vector)
    
    detected = []
    for root in active_roots:
        faulty_outputs = simulate(circuit, vector, fault=root)
        if faulty_outputs != golden_outputs:
            detected.append(root)
            
    return detected

# ==========================================
# 4. D-Algorithm (Simplified ATPG)
# ==========================================
def d_algorithm_generate(circuit, fault):
    fault_node, stuck_val = fault
    desired_activation_val = 1 - stuck_val
    vector = {}
    
    def backtrace(node_name, desired_val):
        node = circuit.nodes[node_name]
        if node.type == "input":
            vector[node_name] = desired_val
            return
            
        if not node.driven_by: return
        
        g_type, ins = node.driven_by
        if g_type in ['and', 'nand']:
            if (g_type == 'and' and desired_val == 1) or (g_type == 'nand' and desired_val == 0):
                for i in ins: backtrace(i, 1)
            else:
                backtrace(ins[0], 0)
        elif g_type in ['or', 'nor']:
            if (g_type == 'or' and desired_val == 0) or (g_type == 'nor' and desired_val == 1):
                for i in ins: backtrace(i, 0)
            else:
                backtrace(ins[0], 1)
        elif g_type in ['not', 'buf']:
            target = 1 - desired_val if g_type == 'not' else desired_val
            backtrace(ins[0], target)
            
    try:
        backtrace(fault_node, desired_activation_val)
    except RecursionError:
        pass 
        
    for pi in circuit.inputs:
        if pi not in vector:
            vector[pi] = random.choice([0, 1])
            
    return vector

# ==========================================
# 5. Main ATPG Loop
# ==========================================
def run_d_algo(circuit_name):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    netlist_path = os.path.join(base_dir, 'circuits', 'expanded_verilog', f'{circuit_name}_expanded.v')
    fault_report_path = os.path.join(base_dir, 'experiment_results', f'fault_report_{circuit_name}.txt')
    
    # Setup Data Logging Directory
    plot_dir = os.path.join(base_dir, 'coverage_results', 'plot_data')
    os.makedirs(plot_dir, exist_ok=True)
    csv_file = os.path.join(plot_dir, f'dalgo_sim_{circuit_name}.csv')
    
    if not os.path.exists(netlist_path) or not os.path.exists(fault_report_path):
        print(f"Error: Missing files for {circuit_name}")
        return

    print(f"[*] Parsing netlist: {netlist_path}")
    circuit = parse_expanded_netlist(netlist_path)
    
    # Use actual parsed fault count to ensure coverage % matches random scripts perfectly
    total_faults = parse_fault_report(fault_report_path)
    
    print("[*] Performing Strict Equivalence Fault Collapsing...")
    equiv_map, uncollapsed_count = build_equivalence_classes(circuit)
    
    # Fallback in case fault report parsing failed or differs slightly
    if total_faults == 0: total_faults = uncollapsed_count

    F = list(equiv_map.keys())
    
    print(f"[*] Total Uncollapsed Faults: {total_faults}")
    print(f"[*] Unique Equivalence Classes (Collapsed Roots): {len(equiv_map)}")
    print(f"[*] Data Log       : {csv_file}")
    
    total_non_collapsed_detected = 0
    vectors_generated = 0
    last_batch_coverage = 0.0
    stop_reason = ""
    
    print("-" * 68)
    print(f"{'Time(s)':<10} | {'Vectors':<10} | {'Detected':<10} | {'Coverage':<10}")
    print("-" * 68)
    
    random.seed(42)
    start_time = time.time()
    
    with open(csv_file, 'w') as f_csv:
        f_csv.write("Vector_Index,Time_Seconds,Total_Detected,Delta_Detected,Coverage_Percent,Delta_Coverage\n")
        
        while True:
            elapsed_time = time.time() - start_time
            coverage_percent = (total_non_collapsed_detected / total_faults) * 100.0
            
            # --- STOP CONDITIONS ---
            if elapsed_time > TIMEOUT_SECONDS:
                stop_reason = "30 Minute Time Limit Exceeded"
                break
                
            if coverage_percent >= TARGET_COVERAGE:
                stop_reason = "95% Coverage Reached"
                break
                
            if not F:
                stop_reason = "All collapsible faults detected (Plateau)"
                break
                
            if vectors_generated > 0 and vectors_generated % BATCH_SIZE == 0:
                improvement = coverage_percent - last_batch_coverage
                if improvement < MIN_IMPROVEMENT:
                    stop_reason = f"Coverage plateaued (<{MIN_IMPROVEMENT}% improvement over {BATCH_SIZE} vectors)"
                    break
                last_batch_coverage = coverage_percent
            # -------------------------------
                
            target_f = random.choice(F)
            vector = d_algorithm_generate(circuit, target_f)
            vectors_generated += 1
            
            detected_roots = compute_detected_roots(circuit, vector, F)
            delta_detected = 0
            
            if detected_roots:
                for root in detected_roots:
                    delta_detected += len(equiv_map[root])
                    F.remove(root)
                    
                total_non_collapsed_detected += delta_detected
                coverage_percent = (total_non_collapsed_detected / total_faults) * 100.0
                print(f"{elapsed_time:<10.1f} | {vectors_generated:<10} | {total_non_collapsed_detected:<10} | {coverage_percent:.2f}%")
            
            delta_coverage = (delta_detected / total_faults) * 100.0
            
            # Write to CSV for MATLAB plotting
            f_csv.write(f"{vectors_generated},{elapsed_time:.4f},{total_non_collapsed_detected},{delta_detected},{coverage_percent:.4f},{delta_coverage:.4f}\n")

    final_time = time.time() - start_time
    print("=" * 68)
    print("FINAL D-ALGORITHM REPORT")
    print("=" * 68)
    print(f"Stop Reason             : {stop_reason}")
    print(f"Total Time              : {final_time:.2f} seconds")
    print(f"Test Vectors Generated  : {vectors_generated}")
    print(f"Full Faults Detected    : {total_non_collapsed_detected} / {total_faults}")
    print(f"Final Coverage          : {coverage_percent:.2f}%")
    print(f"Plot Data Saved To      : {csv_file}")
    print("=" * 68)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/d_algo.py <circuit_name>")
        sys.exit(1)
        
    run_d_algo(sys.argv[1])