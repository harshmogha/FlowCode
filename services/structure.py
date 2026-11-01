"""Turns a validated flowchart graph into a structured program tree.

Statement kinds: input, output, process, if, while, for.
The tree is the common input for the Python generator and the algorithm
text printer, so both always agree with the flowchart.
"""
from .graph import Graph, LOOP_TYPES
from .notes import clean

EXIT = "__exit__"


class StructureError(Exception):
    def __init__(self, message, node_id=None):
        super().__init__(message)
        self.node_id = node_id


def _post_dominators(g: Graph):
    nodes = list(g.nodes)
    universe = set(nodes) | {EXIT}
    succ = {}
    for n in nodes:
        s = g.successors(n)
        succ[n] = s if s else [EXIT]
    pd = {n: set(universe) for n in nodes}
    pd[EXIT] = {EXIT}
    changed = True
    while changed:
        changed = False
        for n in nodes:
            inter = None
            for s in succ[n]:
                inter = set(pd[s]) if inter is None else inter & pd[s]
            new = {n} | (inter or set())
            if new != pd[n]:
                pd[n] = new
                changed = True
    return pd


def _immediate_post_dominator(pd, n):
    strict = pd[n] - {n}
    if not strict:
        return EXIT
    return max(strict, key=lambda p: len(pd[p]))


def build_structure(ir: dict):
    g = Graph(ir)
    starts = g.of_type("start")
    if len(starts) != 1:
        raise StructureError("The flowchart needs exactly one Start block.")
    pd = _post_dominators(g)
    budget = [5000]

    def walk(cur, stops):
        out = []
        while cur is not None and cur not in stops:
            budget[0] -= 1
            if budget[0] < 0:
                raise StructureError("This flowchart is too tangled to convert. Use While/For blocks for repeats.", cur)
            node = g.nodes[cur]
            t = node["type"]
            if t == "start":
                if clean(node.get("note")):
                    out.append({"kind": "comment", "node": node})
                cur = g.target(cur, "next")
            elif t == "end":
                if clean(node.get("note")):
                    out.append({"kind": "comment", "node": node})
                break
            elif t in ("input", "output", "process"):
                out.append({"kind": t, "node": node})
                cur = g.target(cur, "next")
            elif t == "decision":
                join = _immediate_post_dominator(pd, cur)
                join = None if join == EXIT else join
                inner = set(stops) | ({join} if join else set())
                then = walk(g.target(cur, "true"), inner)
                els = walk(g.target(cur, "false"), inner)
                out.append({"kind": "if", "node": node, "then": then, "else": els})
                cur = join
            elif t in LOOP_TYPES:
                body = walk(g.target(cur, "body"), set(stops) | {cur})
                out.append({"kind": t, "node": node, "body": body})
                cur = g.target(cur, "exit")
            else:
                raise StructureError("Unknown block.", cur)
        return out

    return walk(starts[0]["id"], set())
