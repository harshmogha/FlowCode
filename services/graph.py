"""Shared helpers for the flowchart intermediate representation (IR).

IR shape::

    {"nodes": [{"id": "n1", "type": "input", "variable": "n", ...}],
     "edges": [{"source": "n1", "sourceHandle": "next", "target": "n2"}]}

Handle names: next | true | false | body | exit
"""

NODE_TYPES = ("start", "end", "input", "output", "process", "decision", "while", "for")

HANDLES = {
    "start": ["next"],
    "end": [],
    "input": ["next"],
    "output": ["next"],
    "process": ["next"],
    "decision": ["true", "false"],
    "while": ["body", "exit"],
    "for": ["body", "exit"],
}

INPUT_TYPES = ("int", "float", "text", "list_int", "list_float")

TYPE_LABELS = {
    "start": "Start", "end": "End", "input": "Input", "output": "Output",
    "process": "Process", "decision": "Decision", "while": "While loop", "for": "For loop",
}

LOOP_TYPES = ("while", "for")


class Graph:
    """Read-only view over an IR dict."""

    def __init__(self, ir: dict):
        self.nodes = {n["id"]: n for n in ir.get("nodes", [])}
        self.edges = ir.get("edges", [])
        self.out = {nid: {} for nid in self.nodes}      # id -> handle -> [targets]
        self.pred = {nid: [] for nid in self.nodes}     # id -> [sources]
        for e in self.edges:
            s, t = e.get("source"), e.get("target")
            if s in self.nodes and t in self.nodes:
                self.out[s].setdefault(e.get("sourceHandle") or "next", []).append(t)
                self.pred[t].append(s)

    def target(self, nid, handle):
        lst = self.out.get(nid, {}).get(handle, [])
        return lst[0] if lst else None

    def successors(self, nid):
        res = []
        for lst in self.out.get(nid, {}).values():
            res.extend(lst)
        return res

    def of_type(self, *types):
        return [n for n in self.nodes.values() if n["type"] in types]

    def reachable_from(self, start, blocked=()):
        seen, stack = set(), [start]
        while stack:
            cur = stack.pop()
            if cur in seen or cur in blocked:
                continue
            seen.add(cur)
            stack.extend(self.successors(cur))
        return seen
