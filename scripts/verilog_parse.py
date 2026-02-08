from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass(frozen=True)
class Port:
    direction: str  # "input" or "output"
    name: str
    width: int = 1  # scalar default


@dataclass(frozen=True)
class ModuleInfo:
    name: str
    ports: List[Port]
    inputs: List[Port]
    outputs: List[Port]


_COMMENT_LINE = re.compile(r"//.*?$", re.M)
_COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.S)


def _strip_comments(txt: str) -> str:
    txt = _COMMENT_BLOCK.sub("", txt)
    txt = _COMMENT_LINE.sub("", txt)
    return txt


def _bus_width(range_str: Optional[str]) -> int:
    """
    range_str examples: [7:0] or [0:7]
    """
    if not range_str:
        return 1
    m = re.match(r"\[\s*(\d+)\s*:\s*(\d+)\s*\]", range_str.strip())
    if not m:
        return 1
    a, b = int(m.group(1)), int(m.group(2))
    return abs(a - b) + 1


def _split_names(blob: str) -> List[str]:
    # split by comma, remove whitespace, ignore empties
    parts = [p.strip() for p in blob.replace("\n", " ").split(",")]
    return [p for p in parts if p]


def parse_module_ports(verilog_path: str) -> ModuleInfo:
    """
    Parse a simple ISCAS-style verilog netlist to extract module name + input/output decls.
    Works for typical patterns:
      module c17 (N1, N2, ...);
      input N1, N2;
      output N22;
      wire N10, ...;
    """
    text = Path(verilog_path).read_text(encoding="utf-8", errors="ignore")
    text = _strip_comments(text)

    # module name: module <name> (
    mm = re.search(r"\bmodule\s+([A-Za-z_]\w*)\s*\(", text)
    if not mm:
        raise ValueError(f"Cannot find module declaration in {verilog_path}")
    mod_name = mm.group(1)

    ports: List[Port] = []

    # match declarations like:
    # input [3:0] a,b;  input wire a;  output reg y;
    decl_pat = re.compile(
        r"\b(input|output)\b\s*(?:wire|reg)?\s*(\[[^\]]+\])?\s*([^;]+);",
        re.I | re.M,
    )

    for m in decl_pat.finditer(text):
        direction = m.group(1).lower()
        bus = m.group(2)
        names_blob = m.group(3)
        width = _bus_width(bus)
        for name in _split_names(names_blob):
            # defensive: remove accidental trailing/leading tokens
            name = name.strip()
            if not name:
                continue
            ports.append(Port(direction=direction, name=name, width=width))

    inputs = [p for p in ports if p.direction == "input"]
    outputs = [p for p in ports if p.direction == "output"]

    if not inputs or not outputs:
        raise ValueError(
            f"Parsed ports look empty. inputs={len(inputs)} outputs={len(outputs)}. "
            f"Check verilog style in {verilog_path}"
        )

    return ModuleInfo(name=mod_name, ports=ports, inputs=inputs, outputs=outputs)
