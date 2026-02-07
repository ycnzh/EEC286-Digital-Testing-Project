from typing import List, Tuple
from dataclasses import dataclass
from pathlib import Path
import re

@dataclass
class Port:
    direction: str  # input/output
    name: str
    width: int      # 1 for scalar, else bus width

@dataclass
class ModuleInfo:
    name: str
    ports: List[Port]
    inputs: List[Port]
    outputs: List[Port]

def _bus_width(range_str: str) -> int:
    m = re.match(r"\[(\d+)\s*:\s*(\d+)\]", range_str.strip())
    if not m:
        return 1
    a = int(m.group(1))
    b = int(m.group(2))
    return abs(a - b) + 1

def parse_module_ports(verilog_path: str) -> ModuleInfo:
    text = Path(verilog_path).read_text()

    # module name
    mm = re.search(r"\bmodule\s+(\w+)\s*\(", text)
    if not mm:
        raise ValueError("Cannot find module declaration")
    mod_name = mm.group(1)

    ports: List[Port] = []

    for direction in ["input", "output"]:
pattern = rf"\b{direction}\b\s*(?:wire\s+|reg\s+)?(\[[^\]]+\]\s*)?([^;]+);"
        for m in re.finditer(pattern, text):
            bus = m.group(1)
            names = m.group(2)
            width = _bus_width(bus) if bus else 1
            for name in [n.strip() for n in names.split(",")]:
                if not name:
                    continue
                name = re.split(r"\s|//", name)[0].strip()
if name in ("input", "output", "wire", "reg"):
    continue
                ports.append(Port(direction, name, width))

    inputs = [p for p in ports if p.direction == "input"]
    outputs = [p for p in ports if p.direction == "output"]
    return ModuleInfo(
        name=mod_name,
        ports=ports,
        inputs=inputs,
        outputs=outputs
    )

def total_width(ports: List[Port]) -> int:
    return sum(p.width for p in ports)

def pack_order(ports: List[Port]) -> List[Tuple[str, int]]:
    return [(p.name, p.width) for p in ports]


