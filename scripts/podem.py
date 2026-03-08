import sys
import os
import time
import random
import argparse
import re
from collections import defaultdict

# ==========================================
# 1. Netlist Parsing & Data Structures
# ==========================================
class Node:
    def __init__(self, name, node_type="wire"):
        self.name = name
        self.type = node_type 
        self.value = None       # Used for single-value fault dropping
        self.val5 = (None, None) # Used for PODEM 5-value logic (Good, Faulty)
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

# ==========================================
# 2. Strict Equivalence Collapsing
# ==========================================
def build_equivalence_classes(circuit):
    print("[*] Performing Strict Equivalence Fault Collapsing...")
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
        
    print(f"[*] Total Uncollapsed Faults: {len(parent)}")
    print(f"[*] Unique Equivalence Classes (Collapsed Roots): {len(equiv_map)}")
    return equiv_map

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
# 4. PODEM ATPG ENGINE
# ==========================================
def eval_loose(g_type, in_vals):
    """Evaluates logic safely handling Nones (X's)"""
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
    """Forward Implication simulating Good and Faulty circuits simultaneously."""
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
    """Finds the next objective (Node, Value) to activate or propagate the fault."""
    f_node, stuck_val = fault
    f_val5 = circuit.nodes[f_node].val5
    
    # Objective 1: Activate the fault
    if f_val5[0] != 1 - stuck_val:
        return (f_node, 1 - stuck_val)

    # Objective 2: Find a D-Frontier Gate to propagate through
    d_front = []
    for name, node in circuit.nodes.items():
        if node.val5[0] is None or node.val5[1] is None: # Output is X
            if node.driven_by:
                # Is any input holding D or D_bar?
                for i in node.driven_by[1]:
                    v = circuit.nodes[i].val5
                    if v[0] is not None and v[1] is not None and v[0] != v[1]:
                        d_front.append(name)
                        break
                        
    if not d_front: return None # Fault blocked (X-Path exhausted)
    
    # Pick first D-frontier gate and find its non-controlling input value
    gate_name = d_front[0]
    g_type, ins = circuit.nodes[gate_name].driven_by
    nc_val = 1 if g_type in ['and', 'nand'] else 0 
    
    for i in ins:
        if circuit.nodes[i].val5[0] is None:
            return (i, nc_val)
            
    return None

def backtrace(circuit, curr_node, curr_val):
    """Traces an objective backward to a Primary Input."""
    while circuit.nodes[curr_node].type != "input":
        g_type, ins = circuit.nodes[curr_node].driven_by
        if g_type in ['nand', 'nor', 'not']:
            curr_val = 1 - curr_val
            
        # Follow an X path backwards
        for i in ins:
            if circuit.nodes[i].val5[0] is None:
                curr_node = i
                break
    return curr_node, curr_val

def podem_recurse(circuit, fault, pi_assigns, stats):
    if stats['backtracks'] > 50: return False # Backtrack Limit

    imply_5val(circuit, pi_assigns, fault)

    # Check Success: Is fault effect visible at ANY Primary Output?
    for po in circuit.outputs:
        v = circuit.nodes[po].val5
        if v[0] is not None and v[1] is not None and v[0] != v[1]:
            return True

    obj = get_objective(circuit, fault)
    if not obj: return False

    pi, val = backtrace(circuit, obj[0], obj[1])

    # Try standard decision
    pi_assigns[pi] = val
    if podem_recurse(circuit, fault, pi_assigns, stats): return True

    # Try reverse decision (Backtracking)
    stats['backtracks'] += 1
    pi_assigns[pi] = 1 - val
    if podem_recurse(circuit, fault, pi_assigns, stats): return True

    # Undo
    stats['backtracks'] += 1
    del pi_assigns[pi]
    return False

def generate_podem_vector(circuit, fault):
    pi_assigns = {}
    stats = {'backtracks': 0}
    
    success = podem_recurse(circuit, fault, pi_assigns, stats)
    
    # Fill remaining unassigned PIs randomly
    for pi in circuit.inputs:
        if pi not in pi_assigns:
            pi_assigns[pi] = random.choice([0, 1])
            
    return pi_assigns # Even if PODEM aborted, return the partially random vector

# ==========================================
# 5. Main Loop
# ==========================================
def run_atpg(filepath, user_total_faults):
    circuit = parse_expanded_netlist(filepath)
    actual_uncollapsed = len(circuit.nodes) * 2
    if user_total_faults != actual_uncollapsed:
        user_total_faults = actual_uncollapsed

    equiv_map = build_equivalence_classes(circuit)
    F = list(equiv_map.keys())
    
    total_non_col_det = 0
    vectors_generated = 0
    
    print("-" * 65)
    print(f"{'Time(s)':<10} | {'Vectors':<10} | {'Non-Col Detected':<16} | {'Coverage':<10}")
    print("-" * 65)
    
    start_time = time.time()
    
    while True:
        elapsed_time = time.time() - start_time
        coverage = total_non_col_det / user_total_faults
        
        # --- UPDATED STOP CONDITIONS ---
        if elapsed_time > 600:
            print(f"\n[STOP] Time limit of 10 minutes exceeded.")
            print(f"[RESULT] Final Coverage achieved: {coverage*100:.2f}%")
            break
            
        if coverage >= 0.95:
            print(f"{elapsed_time:<10.1f} | {vectors_generated:<10} | {total_non_col_det:<16} | {coverage*100:.2f}%")
            print(f"\n[STOP] Target fault coverage of 95% reached.")
            print(f"[RESULT] Total Run Time: {elapsed_time:.2f} seconds.")
            break
            
        if not F:
            print("\n[STOP] All collapsible faults detected. Coverage plateau.")
            print(f"[RESULT] Plateaued at {coverage*100:.2f}% in {elapsed_time:.2f} seconds.")
            break
        # -------------------------------
            
        target_f = random.choice(F)
        vector = generate_podem_vector(circuit, target_f)
        vectors_generated += 1
        
        detected_roots = compute_detected_roots(circuit, vector, F)
        
        if detected_roots:
            for root in detected_roots:
                total_non_col_det += len(equiv_map[root])
                F.remove(root) 
            coverage = total_non_col_det / user_total_faults
            print(f"{elapsed_time:<10.1f} | {vectors_generated:<10} | {total_non_col_det:<16} | {coverage*100:.2f}%")
        elif vectors_generated % 50 == 0:
            print(f"{elapsed_time:<10.1f} | {vectors_generated:<10} | {total_non_col_det:<16} | {coverage*100:.2f}% (Searching...)")

    final_time = time.time() - start_time
    print("=" * 65)
    print("FINAL PODEM ATPG REPORT")
    print(f"Total Time:             {final_time:.10f} seconds")
    print(f"Test Vectors Generated: {vectors_generated}")
    print(f"Full Faults Detected:   {total_non_col_det} / {user_total_faults}")
    print(f"Final Coverage:         {(total_non_col_det / user_total_faults) * 100:.2f}%")
    print("=" * 65)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("netlist", help="Path to the expanded Verilog netlist")
    parser.add_argument("total_faults", type=int, help="Total non-collapsed faults")
    args = parser.parse_args()
    if not os.path.exists(args.netlist):
        sys.exit(1)
    run_atpg(args.netlist, args.total_faults)