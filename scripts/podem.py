#!/usr/bin/env python3
"""
ISCAS PODEM ATPG Simulator (with CSV Data Logging) - FIXED DEADLOCK
================================================================
- Generates targeted test vectors using Path-Oriented Decision Making.
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
TIMEOUT_SECONDS = 18000     # 300 minutes
TARGET_COVERAGE = 95.0
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
        self.val5 = (None, None) 
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
    faults = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if re.match(r'STEM:(\w+)\s+SA([01])', line) or re.match(r'BRANCH:(\w+)->(\w+)\s+SA([01])', line):
                faults.append(line)
    return len(faults)

# ==========================================
# 2. Strict Equivalence Collapsing
# ==========================================
def build_equivalence_classes(circuit):
    parent = {}
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

    for name, node in circuit.nodes.items():
        if not node.driven_by: continue
        g_type, ins = node.driven_by
        
        if g_type == 'and':
            for inp in ins:
                if len(circuit.nodes[inp].drives) == 1: union((inp, 0), (name, 0))
        elif g_type == 'nand':
            for inp in ins:
                if len(circuit.nodes[inp].drives) == 1: union((inp, 0), (name, 1))
        elif g_type == 'or':
            for inp in ins:
                if len(circuit.nodes[inp].drives) == 1: union((inp, 1), (name, 1))
        elif g_type == 'nor':
            for inp in ins:
                if len(circuit.nodes[inp].drives) == 1: union((inp, 1), (name, 0))
        elif g_type == 'not':
            if len(circuit.nodes[ins[0]].drives) == 1:
                union((ins[0], 0), (name, 1))
                union((ins[0], 1), (name, 0))
        elif g_type == 'buf':
            if len(circuit.nodes[ins[0]].drives) == 1:
                union((ins[0], 0), (name, 0))
                union((ins[0], 1), (name, 1))

    equiv_map = defaultdict(list)
    for fault in parent.keys():
        equiv_map[find(fault)].append(fault)
        
    return equiv_map, len(parent)

# ==========================================
# 3. Fast Single-Value Simulator (For Dropping)
# ==========================================
def eval_single(g_type, in_vals):
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

def simulate_fast(circuit, vector, fault=None):
    for node in circuit.nodes.values():
        node.value = None
    for pi, val in vector.items():
        circuit.nodes[pi].value = fault[1] if (fault and pi == fault[0]) else val
            
    progress = True
    while progress:
        progress = False
        for name, node in circuit.nodes.items():
            if node.value is None and node.driven_by:
                g_type, ins = node.driven_by
                in_vals = [circuit.nodes[i].value for i in ins]
                if None not in in_vals:
                    node.value = fault[1] if (fault and name == fault[0]) else eval_single(g_type, in_vals)
                    progress = True
    return tuple(circuit.nodes[po].value for po in circuit.outputs)

def compute_detected_roots(circuit, vector, active_roots):
    golden = simulate_fast(circuit, vector)
    return [root for root in active_roots if simulate_fast(circuit, vector, fault=root) != golden]

# ==========================================
# 4. PODEM ATPG ENGINE (WITH DEADLOCK FIXES)
# ==========================================
def eval_loose(g_type, in_vals):
    if g_type in ['not', 'buf']:
        if in_vals[0] is None: return None
        return 1 - in_vals[0] if g_type == 'not' else in_vals[0]
    if g_type in ['and', 'nand']:
        if 0 in in_vals: res = 0
        elif None in in_vals: res = None
        else: res = 1
        return 1 - res if g_type == 'nand' and res is not None else res
    if g_type in ['or', 'nor']:
        if 1 in in_vals: res = 1
        elif None in in_vals: res = None
        else: res = 0
        return 1 - res if g_type == 'nor' and res is not None else res
    if g_type in ['xor', 'xnor']:
        if None in in_vals: return None
        res = in_vals[0] ^ in_vals[1]
        return 1 - res if g_type == 'xnor' else res
    return None

def imply_5val(circuit, pi_assigns, fault):
    for n in circuit.nodes.values(): n.val5 = (None, None)
    for pi, v in pi_assigns.items():
        circuit.nodes[pi].val5 = (v, fault[1] if pi == fault[0] else v)

    progress = True
    while progress:
        progress = False
        for name, node in circuit.nodes.items():
            if node.driven_by:
                g_type, ins = node.driven_by
                in_goods = [circuit.nodes[i].val5[0] for i in ins]
                in_faultys = [circuit.nodes[i].val5[1] for i in ins]
                
                good_out = eval_loose(g_type, in_goods)
                faulty_out = fault[1] if name == fault[0] else eval_loose(g_type, in_faultys)
                
                new_val = (good_out, faulty_out)
                if new_val != node.val5:
                    node.val5 = new_val
                    progress = True

def get_objective(circuit, fault):
    f_node, stuck_val = fault
    f_val5 = circuit.nodes[f_node].val5
    
    # [BUG FIX 1] 冲突检测：如果节点已经被赋成了我们不想要的值，必须返回 None 触发回溯
    if f_val5[0] == stuck_val:
        return None 
        
    if f_val5[0] is None:
        return (f_node, 1 - stuck_val)

    d_front = []
    for name, node in circuit.nodes.items():
        if node.val5[0] is None or node.val5[1] is None: 
            if node.driven_by:
                for i in node.driven_by[1]:
                    v = circuit.nodes[i].val5
                    if v[0] is not None and v[1] is not None and v[0] != v[1]:
                        d_front.append(name)
                        break
                        
    if not d_front: return None 
    
    gate_name = d_front[0]
    g_type, ins = circuit.nodes[gate_name].driven_by
    nc_val = 1 if g_type in ['and', 'nand'] else 0 
    
    for i in ins:
        if circuit.nodes[i].val5[0] is None:
            return (i, nc_val)
            
    return None

def backtrace(circuit, curr_node, curr_val):
    while circuit.nodes[curr_node].type != "input":
        g_type, ins = circuit.nodes[curr_node].driven_by
        if g_type in ['nand', 'nor', 'not']:
            curr_val = 1 - curr_val
            
        # [BUG FIX 2] 防御性步进机制，防止所有输入均不为 None 时的死循环
        moved = False
        for i in ins:
            if circuit.nodes[i].val5[0] is None:
                curr_node = i
                moved = True
                break
                
        # 兜底：如果没找到未知状态，强行退一步以打破死锁
        if not moved and ins:
            curr_node = ins[0]
            
    return curr_node, curr_val

def podem_recurse(circuit, fault, pi_assigns, stats):
    if stats['backtracks'] > 50: return False 

    imply_5val(circuit, pi_assigns, fault)

    for po in circuit.outputs:
        v = circuit.nodes[po].val5
        if v[0] is not None and v[1] is not None and v[0] != v[1]:
            return True

    obj = get_objective(circuit, fault)
    if not obj: return False # 如果触发冲突，此处会平滑回溯

    pi, val = backtrace(circuit, obj[0], obj[1])

    pi_assigns[pi] = val
    if podem_recurse(circuit, fault, pi_assigns, stats): return True

    stats['backtracks'] += 1
    pi_assigns[pi] = 1 - val
    if podem_recurse(circuit, fault, pi_assigns, stats): return True

    stats['backtracks'] += 1
    del pi_assigns[pi]
    return False

def generate_podem_vector(circuit, fault):
    pi_assigns = {}
    stats = {'backtracks': 0}
    
    success = podem_recurse(circuit, fault, pi_assigns, stats)
    
    for pi in circuit.inputs:
        if pi not in pi_assigns:
            pi_assigns[pi] = random.choice([0, 1])
            
    return pi_assigns 

# ==========================================
# 5. Main Loop
# ==========================================
def run_podem(circuit_name):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    netlist_path = os.path.join(base_dir, 'circuits', 'expanded_verilog', f'{circuit_name}_expanded.v')
    fault_report_path = os.path.join(base_dir, 'experiment_results', f'{circuit_name}_faults.txt')
    
    # Fallback to the other naming convention if the first one fails
    if not os.path.exists(fault_report_path):
         fault_report_path = os.path.join(base_dir, 'experiment_results', f'fault_report_{circuit_name}.txt')
    
    plot_dir = os.path.join(base_dir, 'coverage_results', 'plot_data')
    os.makedirs(plot_dir, exist_ok=True)
    csv_file = os.path.join(plot_dir, f'podem_sim_{circuit_name}.csv')
    
    if not os.path.exists(netlist_path) or not os.path.exists(fault_report_path):
        print(f"Error: Missing files for {circuit_name}")
        return

    print(f"[*] Parsing netlist: {netlist_path}")
    circuit = parse_expanded_netlist(netlist_path)
    
    total_faults = parse_fault_report(fault_report_path)
    
    print("[*] Performing Strict Equivalence Fault Collapsing...")
    equiv_map, uncollapsed_count = build_equivalence_classes(circuit)
    if total_faults == 0: total_faults = uncollapsed_count

    F = list(equiv_map.keys())
    
    print(f"[*] Total Uncollapsed Faults: {total_faults}")
    print(f"[*] Unique Equivalence Classes (Collapsed Roots): {len(equiv_map)}")
    print(f"[*] Data Log       : {csv_file}")
    
    total_non_col_det = 0
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
            coverage_percent = (total_non_col_det / total_faults) * 100.0
            
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
            vector = generate_podem_vector(circuit, target_f)
            vectors_generated += 1
            
            detected_roots = compute_detected_roots(circuit, vector, F)
            delta_detected = 0
            
            if detected_roots:
                for root in detected_roots:
                    delta_detected += len(equiv_map[root])
                    F.remove(root) 
                    
                total_non_col_det += delta_detected
                coverage_percent = (total_non_col_det / total_faults) * 100.0
                print(f"{elapsed_time:<10.1f} | {vectors_generated:<10} | {total_non_col_det:<10} | {coverage_percent:.2f}%")
            
            delta_coverage = (delta_detected / total_faults) * 100.0
            f_csv.write(f"{vectors_generated},{elapsed_time:.4f},{total_non_col_det},{delta_detected},{coverage_percent:.4f},{delta_coverage:.4f}\n")

    final_time = time.time() - start_time
    print("=" * 68)
    print("FINAL PODEM ATPG REPORT")
    print("=" * 68)
    print(f"Stop Reason             : {stop_reason}")
    print(f"Total Time              : {final_time:.10f} seconds")
    print(f"Test Vectors Generated  : {vectors_generated}")
    print(f"Full Faults Detected    : {total_non_col_det} / {total_faults}")
    print(f"Final Coverage          : {coverage_percent:.2f}%")
    print(f"Plot Data Saved To      : {csv_file}")
    print("=" * 68)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/podem.py <circuit_name>")
        sys.exit(1)
    run_podem(sys.argv[1])