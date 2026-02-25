import re
import os
import sys
import argparse
from collections import defaultdict

# ===========================
# Configuration
# ===========================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
VERILOG_DIR = os.path.join(PROJECT_ROOT, "circuits", "verilog")
EXPANDED_DIR = os.path.join(PROJECT_ROOT, "circuits", "expanded_verilog")
os.makedirs(EXPANDED_DIR, exist_ok=True)

# Verilog Primitives
PRIMITIVES = {'and', 'nand', 'or', 'nor', 'xor', 'xnor', 'not', 'buf'}

class NetlistExpander:
    def __init__(self, circuit_name, input_file, output_file):
        self.circuit_name = circuit_name
        self.filepath = input_file
        self.output_file = output_file
        
        self.content = ""
        self.module_name = ""
        
        # Standard Signals
        self.ports = []
        self.inputs = []
        self.outputs = []
        self.wires = []
        
        # Gates: list of dicts 
        self.gates = []
        
        # Fanout Tracking
        self.fanout_counts = defaultdict(int)
        
        # Expansion Data
        self.new_wires = []
        self.assignments = []
        self.k_counter = 1  # Start naming from K1, K2...

    def load_and_clean(self):
        """Reads file and removes comments and extra whitespace."""
        if not os.path.exists(self.filepath):
            print(f"Error: File not found {self.filepath}")
            sys.exit(1)
        with open(self.filepath, 'r') as f:
            raw = f.read()
        raw = re.sub(r'//.*', ' ', raw)
        raw = re.sub(r'/\*.*?\*/', ' ', raw, flags=re.DOTALL)
        raw = raw.replace('\n', ' ').replace('\r', ' ')
        self.content = re.sub(r'\s+', ' ', raw).strip()

    def parse(self):
        """Parses the netlist into components based on statement keywords."""
        statements = [s.strip() for s in self.content.split(';') if s.strip()]
        for stmt in statements:
            parts = stmt.split(' ', 1)
            keyword = parts[0]
            body = parts[1] if len(parts) > 1 else ""

            if keyword == 'module':
                m = re.match(r'(\w+)\s*\((.*?)\)', body)
                if m:
                    self.module_name = m.group(1)
                    self.ports = [p.strip() for p in m.group(2).split(',') if p.strip()]
            elif keyword == 'input':
                self.inputs.extend([s.strip() for s in body.split(',')])
            elif keyword == 'output':
                self.outputs.extend([s.strip() for s in body.split(',')])
            elif keyword == 'wire':
                self.wires.extend([s.strip() for s in body.split(',')])
            elif keyword in PRIMITIVES:
                self._parse_gate(keyword, body)

    def _parse_gate(self, g_type, body):
        """Extracts gate information and counts usage for fanout analysis."""
        idx_open = body.find('(')
        idx_close = body.rfind(')')
        if idx_open == -1 or idx_close == -1: return

        inst_name = body[:idx_open].strip()
        if not inst_name: inst_name = f"U_{len(self.gates)}"
        
        pins = [p.strip() for p in body[idx_open+1:idx_close].split(',') if p.strip()]
        
        output_pin = pins[0]
        input_pins = pins[1:]
        
        # Track usage for fanout analysis
        for pin in input_pins:
            self.fanout_counts[pin] += 1
            
        self.gates.append({
            'type': g_type,
            'name': inst_name,
            'out': output_pin,
            'ins': input_pins
        })

    def expand_branches(self):
        """Creates unique 'K' wire aliases ONLY if fanout > 1."""
        print(f"--- Analyzing Fanouts for {self.circuit_name} ---")
        
        expanded_count = 0
        
        for gate in self.gates:
            expanded_ins = []
            for original_pin in gate['ins']:
                # ONLY expand if fanout > 1
                if self.fanout_counts[original_pin] > 1:
                    # Generate new wire name: K1, K2, K3...
                    new_w = f"K{self.k_counter}"
                    self.k_counter += 1
                    
                    self.new_wires.append(new_w)
                    self.assignments.append(f"assign {new_w} = {original_pin};")
                    expanded_ins.append(new_w)
                    expanded_count += 1
                else:
                    # Keep original wire
                    expanded_ins.append(original_pin)
            
            # Update gate to use the new isolated branches
            gate['ins'] = expanded_ins
            
        print(f"Expansion Complete: Created {expanded_count} new branch wires (K-series).")

    def write_output(self):
        """Writes the expanded netlist and prints a fault report."""
        lines = []
        lines.append(f"module {self.module_name}_expanded ({', '.join(self.ports)});")
        
        lines.append("\n  // Standard Definitions")
        if self.inputs: lines.append(f"  input {', '.join(self.inputs)};")
        if self.outputs: lines.append(f"  output {', '.join(self.outputs)};")
        if self.wires: lines.append(f"  wire {', '.join(self.wires)};")
        
        if self.new_wires:
            lines.append("\n  // Isolated Branch Wires (Fanout > 1)")
            chunk_size = 8
            for i in range(0, len(self.new_wires), chunk_size):
                lines.append(f"  wire {', '.join(self.new_wires[i:i+chunk_size])};")
            
            lines.append("\n  // Fanout Decoupling Assignments")
            for asn in self.assignments:
                lines.append(f"  {asn}")
            
        lines.append("\n  // Gate Instantiations")
        for g in self.gates:
            all_pins = [g['out']] + g['ins']
            lines.append(f"  {g['type']} {g['name']} ({', '.join(all_pins)});")
            
        lines.append("\nendmodule")
        
        with open(self.output_file, 'w') as f:
            f.write("\n".join(lines))

    def report(self):
        """Calculates total fault sites."""
        unique_sites = set()
        unique_sites.update(self.inputs)
        unique_sites.update(self.outputs)
        unique_sites.update(self.wires)      # Covers all internal stems
        unique_sites.update(self.new_wires)  # Covers all K-series branches
        
        total = len(unique_sites)
        
        print("-" * 40)
        print(f"EXPANSION REPORT: {self.circuit_name}")
        print(f"Original Inputs:    {len(self.inputs)}")
        print(f"Original Outputs:   {len(self.outputs)}")
        print(f"Internal Stems:     {len(self.wires)}")
        print(f"Isolated Branches:  {len(self.new_wires)} (K1...K{self.k_counter-1})")
        print(f"Total Unique Sites: {total}")
        print(f"Total SSA Faults:   {total * 2}")
        print("-" * 40)
        print(f"Saved to: {self.output_file}")

if __name__ == "__main__":
    # Setup Argument Parser
    parser = argparse.ArgumentParser(description="Expand ISCAS netlist branches for Full Fault Injection.")
    parser.add_argument("circuit_name", help="Name of the circuit to process (e.g., c17, c432, c499)")
    
    # Parse the arguments
    args = parser.parse_args()
    circuit_name = args.circuit_name

    # Define dynamic paths based on input
    input_file = os.path.join(VERILOG_DIR, f"{circuit_name}.v")
    output_file = os.path.join(EXPANDED_DIR, f"{circuit_name}_expanded.v")

    print(f"--- Processing {circuit_name} ---")
    
    # Instantiate and run
    expander = NetlistExpander(circuit_name, input_file, output_file)
    expander.load_and_clean()
    expander.parse()
    expander.expand_branches()
    expander.write_output()
    expander.report()