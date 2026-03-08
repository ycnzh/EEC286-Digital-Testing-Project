import sys
import os
import time
import random
import argparse
import re
from collections import defaultdict, deque

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
    print(f"[*] Parsing netlist: {filepath}")
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

# ==========================================
# 2. Strict Equivalence Collapsing (Union-Find)
# ==========================================
def build_equivalence_classes(circuit):
    print("[*] Performing Strict Equivalence Fault Collapsing...")
    
    parent = {}
    
    # 1. Initialize Disjoint Set (Every fault is its own root)
    for name in circuit.nodes:
        parent[(name, 0)] = (name, 0)
        parent[(name, 1)] = (name, 1)
        
    def find(i):
        if parent[i] == i: return i
        parent[i] = find(parent[i])
        return parent[i]

    def union(in_fault, out_fault):
        # We purposely make the OUT_FAULT the root. 
        # This makes ATPG justification much easier later!
        root_in = find(in_fault)
        root_out = find(out_fault)
        if root_in != root_out:
            parent[root_in] = root_out

    # 2. Apply rules ONLY if input fanout is exactly 1
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

    # 3. Build the final mapping
    equiv_map = defaultdict(list)
    for fault in parent.keys():
        root = find(fault)
        equiv_map[root].append(fault)
        
    print(f"[*] Total Uncollapsed Faults: {len(parent)}")
    print(f"[*] Unique Equivalence Classes (Collapsed Roots): {len(equiv_map)}")
    
    return equiv_map

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
    # Reset circuit
    for node in circuit.nodes.values():
        node.value = None
        
    # Apply PI vector 
    for pi, val in vector.items():
        if fault and pi == fault[0]:
            circuit.nodes[pi].value = fault[1]
        else:
            circuit.nodes[pi].value = val
            
    # Streamlined Topological Evaluation
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
        
    # Fill remaining PIs randomly to aid propagation
    for pi in circuit.inputs:
        if pi not in vector:
            vector[pi] = random.choice([0, 1])
            
    return vector

# ==========================================
# 5. Main ATPG Loop
# ==========================================
def run_atpg(filepath, user_total_faults):
    circuit = parse_expanded_netlist(filepath)
    
    # Check for User Error in calculation
    actual_uncollapsed_faults = len(circuit.nodes) * 2
    if user_total_faults != actual_uncollapsed_faults:
        print(f"\n[WARNING] You inputted {user_total_faults} total faults, but the parsed netlist contains exactly {actual_uncollapsed_faults} fault sites (*2). Using {actual_uncollapsed_faults} for mathematically accurate coverage.")
        user_total_faults = actual_uncollapsed_faults

    equiv_map = build_equivalence_classes(circuit)
    
    # F is now just the list of "Root" representative faults
    F = list(equiv_map.keys())
    
    total_non_collapsed_detected = 0
    vectors_generated = 0
    
    print("-" * 65)
    print(f"{'Time(s)':<10} | {'Vectors':<10} | {'Non-Col Detected':<16} | {'Coverage':<10}")
    print("-" * 65)
    
    start_time = time.time()
    
    while True:
        elapsed_time = time.time() - start_time
        coverage = total_non_collapsed_detected / user_total_faults
        
        # --- UPDATED STOP CONDITIONS ---
        if elapsed_time > 600:
            print(f"\n[STOP] Time limit of 10 minutes exceeded.")
            print(f"[RESULT] Final Coverage achieved: {coverage*100:.2f}%")
            break
            
        if coverage >= 0.95:
            # Print final hit before breaking
            print(f"{elapsed_time:<10.1f} | {vectors_generated:<10} | {total_non_collapsed_detected:<16} | {coverage*100:.2f}%")
            print(f"\n[STOP] Target fault coverage of 95% reached.")
            print(f"[RESULT] Total Run Time: {elapsed_time:.2f} seconds.")
            break
            
        if not F:
            print("\n[STOP] All collapsible faults detected. Coverage plateau.")
            print(f"[RESULT] Plateaued at {coverage*100:.2f}% in {elapsed_time:.2f} seconds.")
            break
        # -------------------------------
            
        target_f = random.choice(F)
        vector = d_algorithm_generate(circuit, target_f)
        vectors_generated += 1
        
        detected_roots = compute_detected_roots(circuit, vector, F)
        
        if detected_roots:
            for root in detected_roots:
                # Add the ENTIRE equivalence class size to the detected count
                total_non_collapsed_detected += len(equiv_map[root])
                F.remove(root) # Drop the root from active search
                
            coverage = total_non_collapsed_detected / user_total_faults
            print(f"{elapsed_time:<10.1f} | {vectors_generated:<10} | {total_non_collapsed_detected:<16} | {coverage*100:.2f}%")
        
        # Heartbeat
        elif vectors_generated % 50 == 0:
            print(f"{elapsed_time:<10.1f} | {vectors_generated:<10} | {total_non_collapsed_detected:<16} | {coverage*100:.2f}% (Searching...)")

    final_time = time.time() - start_time
    print("=" * 65)
    print("FINAL ATPG REPORT")
    print(f"Total Time:             {final_time:.2f} seconds")
    print(f"Test Vectors Generated: {vectors_generated}")
    print(f"Full Faults Detected:   {total_non_collapsed_detected} / {user_total_faults}")
    print(f"Final Coverage:         {(total_non_collapsed_detected / user_total_faults) * 100:.2f}%")
    print("=" * 65)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ATPG Loop with Equivalence Collapsing")
    parser.add_argument("netlist", help="Path to the expanded Verilog netlist")
    parser.add_argument("total_faults", type=int, help="Total number of non-collapsed faults (e.g., 46 for c17)")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.netlist):
        print(f"Error: Could not find netlist {args.netlist}")
        sys.exit(1)
        
    run_atpg(args.netlist, args.total_faults)