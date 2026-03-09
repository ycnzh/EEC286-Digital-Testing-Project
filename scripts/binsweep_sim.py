#!/usr/bin/env python3
"""
Universal ISCAS Fault Simulator (2-Phase Random + CSV Logging)
================================================================
- Stops each circuit after 30 minutes.
- Stops if coverage reaches 95%.
- Stops if coverage plateau hit (<0.1% improvement over 5000 vectors).
- Logs per-vector coverage data to a CSV file for MATLAB plotting.
"""

import sys, re, random, os, math, time

# ============================================================
#  CONFIGURATION
# ============================================================

TIMEOUT_SECONDS       = 1800    # 30 minutes per circuit
TARGET_COVERAGE       = 95.0
MIN_IMPROVEMENT       = 0.1     # 0.1% improvement required...
BATCH_SIZE            = 5000    # ...over a batch of 5000 vectors (to allow Phase 2 to work)

STALL_THRESHOLD       = 200     # consecutive misses before targeted mode
TARGETED_RAND_TRIES   = 3000    # random attempts per fault in targeted mode
TARGETED_EXHAUST_BITS = 18      # bits to exhaustively sweep in targeted mode
MAX_EXHAUSTIVE_INPUTS = 20      # use exhaustive enumeration if n_in <= this

ALL_CIRCUITS = [
    'c432'
]

# ============================================================
#  1.  PARSER: expanded_verilog
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

# ============================================================
#  2.  PARSER: fault_report
# ============================================================
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
#  3.  CIRCUIT EVALUATOR
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
#  4.  RUN ONE CIRCUIT
# ============================================================
def run(circuit_name, base_dir=None):
    if base_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    verilog_file = os.path.join(base_dir, 'circuits', 'expanded_verilog', f'{circuit_name}_expanded.v')
    fault_file   = os.path.join(base_dir, 'experiment_results', f'fault_report_{circuit_name}.txt')
    
    # Text and CSV log paths
    out_dir  = os.path.join(base_dir, 'coverage_results')
    plot_dir = os.path.join(out_dir, 'plot_data')
    os.makedirs(plot_dir, exist_ok=True)
    
    out_file = os.path.join(out_dir, f'coverage_{circuit_name}.txt')
    csv_file = os.path.join(plot_dir, f'twophase_sim_{circuit_name}.csv')

    # ---- parse ----
    print(f"[1/4] Parsing netlist  : {verilog_file}")
    inputs, outputs, k_assign, gates = parse_expanded_verilog(verilog_file)

    print(f"[2/4] Parsing faults   : {fault_file}")
    faults = parse_fault_report(fault_file)

    n_in     = len(inputs)
    n_faults = len(faults)
    stop_at  = math.ceil((TARGET_COVERAGE/100.0) * n_faults)

    use_random = (n_in > MAX_EXHAUSTIVE_INPUTS)
    RANDOM_BUDGET = max(5000, 10 * n_faults)
    n_vectors = (2 ** n_in) if not use_random else RANDOM_BUDGET

    print(f"[3/4] Circuit summary:")
    print(f"      Inputs / Outputs / Gates : {n_in} / {len(outputs)} / {len(gates)}")
    print(f"      Faults  : {n_faults}  |  Target ({TARGET_COVERAGE}%) : {stop_at}")
    print(f"      Timeout : {TIMEOUT_SECONDS}s  |  Mode : {'random+targeted' if use_random else 'exhaustive'}")
    print(f"[4/4] Running...\n")

    remaining_set       = set(range(n_faults))
    test_set            = []
    detected            = 0
    vec_examined        = 0
    consecutive_miss    = 0
    last_batch_coverage = 0.0
    
    timeout_hit = False
    plateau_hit = False
    stop_reason = ""
    lines       = []
    random.seed(42)

    def log(s=''):
        print(s)
        lines.append(s)

    t_start = time.time()

    def timed_out():
        return (time.time() - t_start) >= TIMEOUT_SECONDS

    def sim_vec(vec):
        good_net = evaluate(gates, k_assign, inputs, vec, fault=None)
        good_out = tuple(good_net[o] for o in outputs)
        newly = []
        for fi in list(remaining_set):
            fn = evaluate(gates, k_assign, inputs, vec, fault=faults[fi])
            if tuple(fn[o] for o in outputs) != good_out:
                newly.append(fi)
        return newly

    # ================================================================
    #  MAIN SIMULATION LOOP WITH CSV CONTEXT
    # ================================================================
    with open(csv_file, 'w') as f_csv:
        f_csv.write("Vector_Index,Time_Seconds,Total_Detected,Delta_Detected,Coverage_Percent,Delta_Coverage\n")

        # Unified processor for all vectors
        def process_vector(vec, label):
            nonlocal vec_examined, detected, consecutive_miss, last_batch_coverage
            nonlocal plateau_hit, stop_reason
            
            vec_examined += 1
            newly = sim_vec(vec)
            delta = len(newly)
            
            if newly:
                for fi in newly:
                    remaining_set.discard(fi)
                detected += delta
                consecutive_miss = 0
                test_set.append(vec)
                rem = n_faults - detected
                cov = detected / n_faults * 100.0
                t = time.time() - t_start
                vstr = ''.join(str(b) for b in vec)
                if n_in > 24: vstr = vstr[:24] + '...'
                log(f"  [{label}] v={vstr}  +{delta:3d} | det={detected:4d} rem={rem:4d} cov={cov:5.2f}%  [{t:.1f}s]")
            elif label == 'Phase1':
                consecutive_miss += 1
                
            curr_cov = (detected / n_faults) * 100.0
            delta_cov = (delta / n_faults) * 100.0
            elapsed = time.time() - t_start
            
            # Log to CSV
            f_csv.write(f"{vec_examined},{elapsed:.4f},{detected},{delta},{curr_cov:.4f},{delta_cov:.4f}\n")
            
            # Check for plateau
            if vec_examined > 0 and vec_examined % BATCH_SIZE == 0:
                if (curr_cov - last_batch_coverage) < MIN_IMPROVEMENT:
                    plateau_hit = True
                    stop_reason = f"Coverage plateaued (<{MIN_IMPROVEMENT}% improvement over {BATCH_SIZE} vectors)"
                last_batch_coverage = curr_cov
                
            return len(newly) > 0

        # ---- header ----
        log("=" * 68)
        log(f"  ISCAS {circuit_name} – Iterative Test Generation + Fault Dropping")
        log("-" * 68)

        log("\n[Phase 1] Main loop\n")

        for vi in range(n_vectors):
            if timed_out():
                timeout_hit = True
                stop_reason = f"{TIMEOUT_SECONDS}s Time Limit Exceeded"
                break
            if detected >= stop_at:
                stop_reason = f"{TARGET_COVERAGE}% Coverage Reached"
                break
            if plateau_hit:
                break

            vec = ([random.randint(0, 1) for _ in range(n_in)]
                   if use_random else [(vi >> (n_in - 1 - b)) & 1 for b in range(n_in)])

            process_vector(vec, 'Phase1')

            # ============================================================
            #  PHASE 2 – targeted mode on stall
            # ============================================================
            if (not timeout_hit and not plateau_hit and consecutive_miss >= STALL_THRESHOLD and remaining_set):
                log(f"\n[Phase 2 – TARGETED] {consecutive_miss} misses → targeting {len(remaining_set)} remaining faults\n")
                consecutive_miss = 0

                rem_list = list(remaining_set)
                random.shuffle(rem_list)

                for fi in rem_list:
                    if timed_out(): timeout_hit = True; stop_reason = f"{TIMEOUT_SECONDS}s Time Limit Exceeded"; break
                    if detected >= stop_at: stop_reason = f"{TARGET_COVERAGE}% Coverage Reached"; break
                    if plateau_hit: break
                    if fi not in remaining_set: continue

                    found = False

                    # 2a. Random targeted tries
                    for _ in range(TARGETED_RAND_TRIES):
                        if timed_out(): timeout_hit = True; stop_reason = f"{TIMEOUT_SECONDS}s Time Limit Exceeded"; break
                        if plateau_hit or fi not in remaining_set: break
                        
                        vec2 = [random.randint(0, 1) for _ in range(n_in)]
                        if process_vector(vec2, 'Targeted'):
                            found = True
                            break

                    if timeout_hit or plateau_hit: break
                    if found or fi not in remaining_set: continue

                    # 2b. Partial exhaustive
                    ebits = min(TARGETED_EXHAUST_BITS, n_in)
                    for mask in range(2 ** ebits):
                        if timed_out(): timeout_hit = True; stop_reason = f"{TIMEOUT_SECONDS}s Time Limit Exceeded"; break
                        if plateau_hit or fi not in remaining_set: break
                        
                        base = [random.randint(0, 1)] * n_in
                        for b in range(ebits):
                            base[b] = (mask >> (ebits - 1 - b)) & 1
                            
                        if process_vector(base, 'Exhaustive'):
                            found = True
                            break

                    if timeout_hit or plateau_hit: break

    # ================================================================
    #  FINAL REPORT
    # ================================================================
    elapsed_total    = time.time() - t_start
    remaining_faults = [faults[fi] for fi in remaining_set]
    
    if not stop_reason:
        stop_reason = "VECTORS EXHAUSTED"

    log("\n" + "=" * 68)
    log("  FINAL REPORT")
    log("=" * 68)
    log(f"  Circuit          : {circuit_name}")
    log(f"  Stop reason      : {stop_reason}")
    log(f"  Total faults     : {n_faults}")
    log(f"  Detected faults  : {detected}")
    log(f"  Remaining faults : {n_faults - detected}")
    log(f"  Fault coverage   : {detected / n_faults * 100:.2f}%")
    log(f"  Test set size    : {len(test_set)} vectors")
    log(f"  Vectors examined : {vec_examined}")
    log(f"  Elapsed time     : {elapsed_total:.2f}s")
    log("-" * 68)
    log(f"  Plot Data Saved  : {csv_file}")
    log("=" * 68)

    with open(out_file, 'w') as f:
        f.write('\n'.join(lines) + '\n')

    print(f"\nResults saved → {out_file}")
    final_cov = detected / n_faults * 100.0
    return final_cov, timeout_hit

# ============================================================
#  5.  ENTRY POINT
# ============================================================
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 scripts/fault_sim.py <circuit>   # single circuit")
        print("  python3 scripts/fault_sim.py all         # all circuits")
        print(f"\nAvailable: {', '.join(ALL_CIRCUITS)}")
        sys.exit(1)

    arg = sys.argv[1].lower()
    circuits = ALL_CIRCUITS if arg == 'all' else [arg]
    summary = []

    for circuit in circuits:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        vf = os.path.join(base_dir, 'circuits', 'expanded_verilog', f'{circuit}_expanded.v')
        ff = os.path.join(base_dir, 'experiment_results', f'fault_report_{circuit}.txt')

        if not os.path.exists(vf):
            msg = f"  SKIP {circuit:8s} – missing {vf}"
            print(msg)
            summary.append((circuit, None, None, 'MISSING netlist'))
            continue
        if not os.path.exists(ff):
            msg = f"  SKIP {circuit:8s} – missing {ff}"
            print(msg)
            summary.append((circuit, None, None, 'MISSING fault report'))
            continue

        print(f"\n{'='*68}")
        print(f"  Starting circuit: {circuit}")
        print(f"{'='*68}\n")

        try:
            cov, timed_out_flag = run(circuit)
            status = 'TIMEOUT' if timed_out_flag else 'OK'
            summary.append((circuit, cov, timed_out_flag, status))
        except Exception as e:
            print(f"  ERROR running {circuit}: {e}")
            summary.append((circuit, None, None, f'ERROR: {e}'))

    if len(circuits) > 1:
        print(f"\n{'='*68}")
        print("  BATCH SUMMARY")
        print(f"{'='*68}")
        print(f"  {'Circuit':<10} {'Coverage':>10}  {'Time':>8}  Status")
        print(f"  {'-'*10} {'-'*10}  {'-'*8}  {'-'*20}")
        for circuit, cov, to, status in summary:
            cov_str = f"{cov:8.2f}%" if cov is not None else "     N/A"
            to_str  = "TIMEOUT" if to else "      OK"
            print(f"  {circuit:<10} {cov_str}  {to_str}  {status}")
        print(f"{'='*68}\n")