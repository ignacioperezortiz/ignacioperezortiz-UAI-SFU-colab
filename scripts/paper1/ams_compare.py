"""Check that two versions of OPF.ams differ only by moved procedures and new sections / comments.

Reports: identifiers added or lost; procedures whose text changed; global declarations (everything except sections,
procedures and their local arguments) whose text or ORDER changed. The order matters: AllConstraints and AllVariables
follow the declaration order, which is the row / column order of the generated matrices.

Usage (from the repository root):
  git show <old commit>:MainProject/OPF.ams > old.ams
  python scripts/paper1/ams_compare.py old.ams MainProject/OPF.ams
Exit code 0 = only moves (and section / read-me comments) changed.
"""
import re
import sys
from collections import Counter

KINDS = ("Section", "DeclarationSection", "Procedure", "Function", "Parameter", "StringParameter", "ElementParameter",
         "Set", "Index", "Variable", "Constraint", "MathematicalProgram", "File", "Macro", "Quantity", "Model",
         "UnitParameter", "Assertion", "DatabaseTable", "DatabaseProcedure", "ExternalProcedure", "ExternalFunction")
HEAD = re.compile(r"^(\t*)(" + "|".join(KINDS) + r")\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{\s*$")


def load(path):
    lines = open(path, encoding="utf-8", newline="").read().replace("\r\n", "\n").split("\n")
    nodes, stack = [], []
    for i, l in enumerate(lines):
        m = HEAD.match(l)
        if m:
            stack.append((m.group(2), m.group(3), i, len(m.group(1))))
            continue
        if stack and l == "\t" * stack[-1][3] + "}":
            kind, name, s, d = stack.pop()
            local = any(x[0] in ("Procedure", "Function") for x in stack)
            sec = next((x[1] for x in reversed(stack) if x[0] == "Section"), "")
            nodes.append(dict(kind=kind, name=name, text=lines[s:i + 1], s=s, local=local, sec=sec))
    if stack:
        sys.exit(f"{path}: unclosed node {stack[-1][:2]}")
    return nodes


a, b = load(sys.argv[1]), load(sys.argv[2])
bad = 0
ca, cb = Counter((n["kind"], n["name"]) for n in a if not n["local"]), Counter((n["kind"], n["name"]) for n in b if not n["local"])
lost, added = ca - cb, cb - ca
if lost:
    bad += 1
    print("LOST:", sorted(lost))
print("added:", sorted(added) or "nothing")

pa = {n["name"]: n for n in a if n["kind"] in ("Procedure", "Function")}
pb = {n["name"]: n for n in b if n["kind"] in ("Procedure", "Function")}
changed = [p for p in pa if p in pb and pa[p]["text"] != pb[p]["text"]]
moved = [p for p in pa if p in pb and pa[p]["sec"] != pb[p]["sec"]]
if changed:
    bad += 1
    print("PROCEDURES WITH CHANGED TEXT:", changed)
print(f"procedures: {len(pa)} -> {len(pb)}, moved to another section: {len(moved)}, text changed: {len(changed)}")

glob = lambda ns: [n for n in sorted(ns, key=lambda n: n["s"])
                   if not n["local"] and n["kind"] not in ("Procedure", "Function", "Section", "DeclarationSection", "Model")]
ga, gb = glob(a), glob(b)
ka, kb = [(n["kind"], n["name"]) for n in ga], [(n["kind"], n["name"]) for n in gb]
common = set(ka) & set(kb)
new_decl, gone_decl = [k for k in kb if k not in common], [k for k in ka if k not in common]
if gone_decl:
    bad += 1
    print("DECLARATIONS REMOVED:", gone_decl)
if new_decl:
    print("declarations added:", new_decl)
order_ok = [k for k in ka if k in common] == [k for k in kb if k in common]
mat = lambda ks: [k for k in ks if k[0] in ("Variable", "Constraint")]
matrix_ok = mat(ka) == mat(kb)
if not order_ok:
    bad += 1
    print("ORDER OF THE EXISTING DECLARATIONS CHANGED")
if not matrix_ok:
    bad += 1
    print("VARIABLES / CONSTRAINTS ADDED, REMOVED OR REORDERED (generated matrices change)")
db = {(n["kind"], n["name"]): n for n in gb}
dch = [n["name"] for n in ga if (n["kind"], n["name"]) in db and n["text"] != db[(n["kind"], n["name"])]["text"]]
if dch:
    bad += 1
    print("DECLARATIONS WITH CHANGED TEXT:", dch)
print(f"global declarations: {len(ga)} -> {len(gb)} ({len(new_decl)} added), order of existing ones identical: {order_ok}, "
      f"variables/constraints identical and in order: {matrix_ok}, text changed: {len(dch)}")
print("OK: only moved procedures and new sections / comments" if not bad else "DIFFERENCES FOUND (see above)")
sys.exit(1 if bad else 0)
