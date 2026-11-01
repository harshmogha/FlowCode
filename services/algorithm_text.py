"""Algorithm text <-> flowchart.

Text syntax (keywords are not case sensitive)::

    START
    INPUT n : int "Enter a number"      types: int, float, text, list, floatlist
    SET total = total + n               also:  total <- total + n
    PRINT "Sum is", total
    IF n mod 2 = 0 THEN ... ELSE ... END IF        (ELSE IF is allowed)
    WHILE n > 0 DO ... END WHILE
    FOR i FROM 1 TO n [STEP 1] DO ... END FOR
    END
"""
import re

from .expression import (ExprError, check_variable_name, parse_expression, parse_expression_list, parse_target,
                         parse_variable_list)
from .flow_validator import validate_ir
from .graph import Graph
from .notes import clean, one_line
from .structure import StructureError, build_structure

TYPE_TO_TEXT = {"int": "int", "float": "float", "text": "text", "list_int": "list", "list_float": "floatlist"}
TEXT_TO_TYPE = {v: k for k, v in TYPE_TO_TEXT.items()}
TYPE_WORDS = {
    "int": "a whole number", "float": "a decimal number", "text": "text",
    "list_int": "a list of whole numbers", "list_float": "a list of decimal numbers",
}


# ---------------------------------------------------------------- printer ---
def _note_lines(node, pad):
    text = clean(node.get("note"))
    return [(f"{pad}// {line}").rstrip() for line in text.split("\n")] if text else []


def print_algorithm(ir: dict) -> str:
    tree = build_structure(ir)
    g = Graph(ir)
    starts, ends = g.of_type("start"), g.of_type("end")
    lines = _note_lines(starts[0], "") if starts else []
    lines.append("START")
    _print_block(tree, 0, lines)
    if len(ends) == 1:                       # with several End blocks the notes cannot be placed in text
        lines.extend(_note_lines(ends[0], ""))
    lines.append("END")
    return "\n".join(lines) + "\n"


def _print_block(stmts, depth, lines):
    pad = "    " * depth
    for s in stmts:
        k, n = s["kind"], s["node"]
        if k == "comment":
            continue
        if k != "if":
            lines.extend(_note_lines(n, pad))
        if k == "input":
            line = f"INPUT {n['variable'].strip()} : {TYPE_TO_TEXT[n.get('varType') or 'int']}"
            if (n.get("prompt") or "").strip():
                line += ' "' + n["prompt"].strip().replace('"', "'") + '"'
            lines.append(pad + line)
        elif k == "output":
            lines.append(f"{pad}PRINT {n['value'].strip()}")
        elif k == "process":
            lines.append(f"{pad}SET {n['variable'].strip()} = {n['expression'].strip()}")
        elif k == "if":
            _print_if(s, depth, lines, "IF")
            lines.append(f"{pad}END IF")
        elif k == "while":
            lines.append(f"{pad}WHILE {n['condition'].strip()} DO")
            _print_block(s["body"], depth + 1, lines)
            lines.append(f"{pad}END WHILE")
        elif k == "for":
            step = f" STEP {n['step'].strip()}" if str(n.get("step") or "").strip() else ""
            lines.append(f"{pad}FOR {n['variable'].strip()} FROM {n['from'].strip()} TO {n['to'].strip()}{step} DO")
            _print_block(s["body"], depth + 1, lines)
            lines.append(f"{pad}END FOR")


def _print_if(s, depth, lines, word):
    pad = "    " * depth
    lines.extend(_note_lines(s["node"], pad))
    lines.append(f"{pad}{word} {s['node']['condition'].strip()} THEN")
    _print_block(s["then"], depth + 1, lines)
    els = s["else"]
    if len(els) == 1 and els[0]["kind"] == "if":
        _print_if(els[0], depth, lines, "ELSE IF")
    elif els:
        lines.append(f"{pad}ELSE")
        _print_block(els, depth + 1, lines)


def describe_steps(ir: dict):
    """Plain-English steps, as a list of {"text", "depth"}."""
    tree = build_structure(ir)
    steps = [{"text": "Start", "depth": 0}]

    def add_note(n, depth):
        text = one_line(n.get("note"))
        if text:
            steps.append({"depth": depth, "text": "Note: " + text})

    def block(stmts, depth):
        for s in stmts:
            k, n = s["kind"], s["node"]
            if k == "comment":
                add_note(n, depth)
                continue
            if k == "input":
                names = [x.strip() for x in n["variable"].split(",")]
                if len(names) > 1:
                    plural = {"int": "whole numbers", "float": "decimal numbers", "text": "words"}.get(n.get("varType") or "int", "values")
                    steps.append({"depth": depth, "text":
                                  f"Read {len(names)} {plural} typed on one line (separated by spaces) and store them in {', '.join(names)}"})
                else:
                    steps.append({"depth": depth, "text":
                                  f"Read {TYPE_WORDS[n.get('varType') or 'int']} from the user and store it in {names[0]}"})
            elif k == "output":
                steps.append({"depth": depth, "text": f"Show {n['value'].strip()}"})
            elif k == "process":
                steps.append({"depth": depth, "text": f"Set {n['variable'].strip()} to {n['expression'].strip()}"})
            elif k == "if":
                steps.append({"depth": depth, "text": f"Check if {n['condition'].strip()}"})
                add_note(n, depth + 1)
                steps.append({"depth": depth + 1, "text": "If yes:"})
                block(s["then"], depth + 2)
                if s["else"]:
                    steps.append({"depth": depth + 1, "text": "If no:"})
                    block(s["else"], depth + 2)
            elif k == "while":
                steps.append({"depth": depth, "text": f"Repeat while {n['condition'].strip()}:"})
                add_note(n, depth + 1)
                block(s["body"], depth + 1)
            elif k == "for":
                step = f" in steps of {n['step'].strip()}" if str(n.get("step") or "").strip() else ""
                steps.append({"depth": depth, "text":
                              f"For {n['variable'].strip()} from {n['from'].strip()} to {n['to'].strip()}{step}:"})
                add_note(n, depth + 1)
                block(s["body"], depth + 1)
            if k in ("input", "output", "process"):
                add_note(n, depth + 1)

    block(tree, 0)
    steps.append({"text": "End", "depth": 0})
    return steps


# ----------------------------------------------------------------- parser ---
class AlgorithmSyntaxError(Exception):
    def __init__(self, line, message, col=None, length=None):
        super().__init__(message)
        self.line = line
        self.message = message
        self.col = col
        self.length = length


_ASSIGN_RE = re.compile(r"^([A-Za-z_]\w*(?:\[.+?\])?)\s*(?:<-|\u2190|:=|(?<![=!<>])=(?!=))\s*(.+)$")
_INPUT_RE = re.compile(r"""^INPUT\s+([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)\s*(?::\s*(\w+))?\s*(?:["'](.*)["'])?\s*$""", re.I)
_FOR_RE = re.compile(r"^FOR\s+([A-Za-z_]\w*)\s+FROM\s+(.+?)\s+TO\s+(.+?)(?:\s+STEP\s+(.+?))?(?:\s+DO)?\s*$", re.I)


class _Parser:
    def __init__(self, text):
        self.lines = []
        self.raw = {}
        self.errors = []
        self.notes = {}              # line number -> note text (comment lines written just above it)
        self.start_note = ""
        self.end_note = ""
        pending = []
        for i, raw in enumerate(text.splitlines(), start=1):
            self.raw[i] = raw.rstrip()
            s = raw.strip()
            if s.startswith("//") or s.startswith("#"):
                pending.append(re.sub(r"^(//|#)\s?", "", s))
            elif s:
                self.lines.append((i, s))
                if pending:
                    self.notes[i] = "\n".join(pending).strip()
                    pending = []
        self.pos = 0

    def peek(self):
        return self.lines[self.pos] if self.pos < len(self.lines) else (None, None)

    def locate(self, line, fragment=None):
        """Column and length of `fragment` inside the source line (whole line if unknown)."""
        raw = self.raw.get(line, "")
        indent = len(raw) - len(raw.lstrip())
        if fragment:
            idx = raw.lower().find(str(fragment).strip().lower())
            if idx >= 0:
                return idx, len(str(fragment).strip())
        return indent, max(1, len(raw.strip()))

    def add_error(self, line, message, fragment=None):
        col, length = self.locate(line, fragment)
        self.errors.append({"line": line, "message": message, "text": self.raw.get(line, ""),
                            "col": col, "length": length})

    def check(self, line, label, fn, fragment=None):
        """Run an expression check. A bad expression is recorded and parsing continues."""
        try:
            fn()
            return True
        except ExprError as ex:
            self.add_error(line, f"{label}: {ex}", fragment)
            return False

    def fail(self, line, message, fragment=None):
        col, length = self.locate(line, fragment)
        raise AlgorithmSyntaxError(line, message, col, length)

    def parse_program(self):
        if self.peek()[1] and self.peek()[1].upper() == "START":
            self.start_note = self.notes.get(self.peek()[0], "")
            self.pos += 1
        stmts = self.parse_block(set())
        line, s = self.peek()
        if s is not None:
            if s.upper() == "END":
                self.end_note = self.notes.get(line, "")
                self.pos += 1
                if self.peek()[1] is not None:
                    self.fail(self.peek()[0], "Nothing can come after END.")
            else:
                self.fail(line, f"Unexpected '{s}'. There is no matching IF, WHILE or FOR above it.")
        return stmts

    def parse_block(self, terminators):
        stmts = []
        while True:
            line, s = self.peek()
            if s is None:
                return stmts
            up = s.upper()
            word = re.split(r"[\s(]", up, maxsplit=1)[0]
            if up == "END" or word == "ELSE" or (word == "END" and up != "END"):
                return stmts
            self.pos += 1
            if word == "INPUT":
                stmts.append(self.parse_input(line, s))
            elif word in ("PRINT", "OUTPUT"):
                value = s[len(word):].strip()
                self.check(line, "PRINT", lambda: parse_expression_list(value), value)
                stmts.append({"kind": "output", "node": {"type": "output", "value": value, "line": line}})
            elif word == "SET":
                stmts.append(self.parse_assign(line, s[3:].strip()))
            elif word == "IF":
                stmts.append(self.parse_if(line, s))
            elif word == "WHILE":
                cond = re.sub(r"^WHILE\s+|\s+DO$", "", s, flags=re.I).strip()
                self.check(line, "WHILE condition", lambda: parse_expression(cond, True), cond)
                body = self.parse_block(set())
                self.expect_end(line, "END WHILE")
                if not body:
                    self.fail(line, "The loop body is empty. Add at least one step between WHILE and END WHILE.")
                stmts.append({"kind": "while", "node": {"type": "while", "condition": cond, "line": line}, "body": body})
            elif word == "FOR":
                stmts.append(self.parse_for(line, s))
            else:
                stmts.append(self.parse_assign(line, s))
            if line in self.notes and stmts:
                stmts[-1]["node"]["note"] = self.notes[line]

    def expect_end(self, start_line, text):
        line, s = self.peek()
        if s is None or not s.upper().startswith(text):
            self.fail(start_line, f"Missing '{text}' for the block that starts here (line {start_line}).")
        self.pos += 1

    def parse_input(self, line, s):
        m = _INPUT_RE.match(s)
        if not m:
            self.fail(line, 'Use: INPUT name : int "Prompt text"')
        var, typ, prompt = m.group(1), (m.group(2) or "int").lower(), m.group(3) or ""
        if typ not in TEXT_TO_TYPE:
            self.fail(line, f"Unknown input type '{typ}'. Use int, float, text, list or floatlist.", typ)
        self.check(line, "INPUT", lambda: parse_variable_list(var), var)
        if "," in var and typ not in ("int", "float", "text"):
            self.fail(line, "Several names can only be read as int, float or text (not a list).", typ)
        return {"kind": "input", "node": {"type": "input", "variable": re.sub(r"\s*,\s*", ", ", var.strip()),
                                          "varType": TEXT_TO_TYPE[typ],
                                          "prompt": prompt, "line": line}}

    def parse_assign(self, line, s):
        m = _ASSIGN_RE.match(s)
        if not m:
            self.fail(line, f"I don't understand '{s}'. Start the line with SET, PRINT, INPUT, IF, WHILE or FOR, "
                            "or write: name = value")
        target, expr = m.group(1), m.group(2).strip()
        self.check(line, "SET", lambda: parse_target(target), target)
        self.check(line, "SET", lambda: parse_expression(expr), expr)
        return {"kind": "process", "node": {"type": "process", "variable": target, "expression": expr, "line": line}}

    def parse_if(self, line, s):
        cond = re.sub(r"^(ELSE\s+)?IF\s+|\s+THEN$", "", s, flags=re.I).strip()
        self.check(line, "IF condition", lambda: parse_expression(cond, True), cond)
        then = self.parse_block(set())
        node = {"type": "decision", "condition": cond, "line": line}
        l2, s2 = self.peek()
        if s2 is not None and s2.upper().startswith("ELSE IF"):
            self.pos += 1
            nested = self.parse_if(l2, s2)
            if l2 in self.notes:
                nested["node"]["note"] = self.notes[l2]
            return {"kind": "if", "node": node, "then": then, "else": [nested]}
        els = []
        if s2 is not None and s2.upper() == "ELSE":
            self.pos += 1
            els = self.parse_block(set())
        self.expect_end(line, "END IF")
        return {"kind": "if", "node": node, "then": then, "else": els}

    def parse_for(self, line, s):
        m = _FOR_RE.match(s)
        if not m:
            self.fail(line, "Use: FOR i FROM 1 TO n [STEP 1] DO")
        var, a, b, step = m.group(1), m.group(2).strip(), m.group(3).strip(), (m.group(4) or "").strip()
        self.check(line, "FOR", lambda: check_variable_name(var), var)
        for label, e in (("FROM", a), ("TO", b), ("STEP", step)):
            if e or label != "STEP":
                self.check(line, label, lambda e=e: parse_expression(e), e)
        body = self.parse_block(set())
        self.expect_end(line, "END FOR")
        if not body:
            self.fail(line, "The loop body is empty. Add at least one step between FOR and END FOR.")
        return {"kind": "for", "node": {"type": "for", "variable": var, "from": a, "to": b, "step": step,
                                        "line": line}, "body": body}

# ------------------------------------------------------- tree -> IR layout ---
HALF = 100          # half the width of a block's slot
PITCH = 135         # vertical distance between block rows
GAP = 40


def _ext(stmts):
    left = right = 0
    for s in stmts:
        k = s["kind"]
        if k == "if":
            ll, lr = _ext(s["then"])
            rl, rr = _ext(s["else"])
            cl = min(-HALF, -(GAP / 2) - lr)
            cr = max(HALF, GAP / 2 + rl)
            e = (max(HALF, -cl + ll), max(HALF, cr + rr))
        elif k in ("while", "for"):
            bl, br = _ext(s["body"])
            e = (max(HALF, bl) + 40, max(HALF, br) + 70)
        else:
            e = (HALF, HALF)
        left, right = max(left, e[0]), max(right, e[1])
    return left, right


class _Builder:
    def __init__(self):
        self.nodes, self.edges, self.count = [], [], 0

    def new(self, ntype, cx, y, fields=None):
        self.count += 1
        node = {"id": f"n{self.count}", "type": ntype, "pos": {"x": cx - HALF, "y": y}}
        node.update(fields or {})
        self.nodes.append(node)
        return node["id"]

    def link(self, tails, target, target_handle="in"):
        for src, handle in tails:
            self.edges.append({"source": src, "sourceHandle": handle, "target": target, "targetHandle": target_handle})

    def place(self, stmts, cx, y):
        entry, tails = None, []
        for s in stmts:
            k, fields = s["kind"], {kk: vv for kk, vv in s["node"].items() if kk != "type"}
            if k in ("input", "output", "process"):
                nid = self.new(k, cx, y, fields)
                if entry is None:
                    entry = nid
                self.link(tails, nid)
                tails, y = [(nid, "next")], y + PITCH
            elif k == "if":
                d = self.new("decision", cx, y, fields)
                if entry is None:
                    entry = d
                self.link(tails, d)
                ll, lr = _ext(s["then"])
                rl, rr = _ext(s["else"])
                cl = cx + min(-HALF, -(GAP / 2) - lr)
                cr = cx + max(HALF, GAP / 2 + rl)
                y0 = y + PITCH
                new_tails, ends = [], [y0]
                for handle, branch, bx in (("true", s["then"], cl), ("false", s["else"], cr)):
                    if branch:
                        e, t, ye = self.place(branch, bx, y0)
                        self.link([(d, handle)], e)
                        new_tails += t
                        ends.append(ye)
                    else:
                        new_tails.append((d, handle))
                tails, y = new_tails, max(ends)
            else:  # while / for
                lo = self.new(k, cx, y, fields)
                if entry is None:
                    entry = lo
                self.link(tails, lo)
                e, t, ye = self.place(s["body"], cx, y + PITCH)
                self.link([(lo, "body")], e)
                self.link(t, lo, "return")
                tails, y = [(lo, "exit")], ye
        return entry, tails, y


def parse_algorithm(text: str):
    """Return {"ok", "ir", "errors"}; errors are {"line", "message", "text", "col", "length"}."""
    parser = _Parser(text or "")
    try:
        tree = parser.parse_program()
    except AlgorithmSyntaxError as ex:
        parser.errors.append({"line": ex.line, "message": ex.message, "text": parser.raw.get(ex.line, ""),
                              "col": ex.col or 0, "length": ex.length or 1})
    if parser.errors:
        errors = sorted(parser.errors, key=lambda e: e["line"])
        return {"ok": False, "ir": None, "errors": errors}

    b = _Builder()
    left, _ = _ext(tree)
    cx = left + 40
    start = b.new("start", cx, 40, {"note": parser.start_note} if parser.start_note else None)
    entry, tails, y = b.place(tree, cx, 40 + PITCH)
    end = b.new("end", cx, y, {"note": parser.end_note} if parser.end_note else None)
    first = entry or end
    b.link([(start, "next")], first)
    b.link(tails, end)
    ir = {"language": "python", "mode": "algorithm", "nodes": b.nodes, "edges": b.edges}
    return {"ok": True, "ir": ir, "errors": []}


def check_algorithm(text: str):
    """Syntax errors plus meaning problems (e.g. unknown variables), all with line numbers."""
    res = parse_algorithm(text)
    if not res["ok"]:
        return {"ok": False, "errors": res["errors"], "warnings": [], "ir": None}
    lines = (text or "").splitlines()
    node_line = {n["id"]: n.get("line") for n in res["ir"]["nodes"]}
    problems = []
    for issue in validate_ir(res["ir"])["errors"]:
        line = node_line.get(issue["nodeId"])
        raw = lines[line - 1].rstrip() if line else ""
        indent = len(raw) - len(raw.lstrip())
        problems.append({"line": line, "message": issue["message"], "text": raw,
                         "col": indent, "length": max(1, len(raw.strip()))})
    problems.sort(key=lambda e: e["line"] or 0)
    return {"ok": True, "errors": [], "warnings": problems, "ir": res["ir"]}


def safe_print(ir):
    """Print algorithm text; returns (text, error_message)."""
    check = validate_ir(ir)
    if not check["valid"]:
        return None, check["errors"][0]["message"]
    try:
        return print_algorithm(ir), None
    except StructureError as ex:
        return None, str(ex)