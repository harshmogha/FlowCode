"""Validates a flowchart IR and returns friendly, node-linked messages."""
from .expression import (ExprError, check_variable_name, parse_expression,
                         parse_expression_list, parse_target, parse_variable_list, IDENT_RE)
from .graph import HANDLES, INPUT_TYPES, LOOP_TYPES, NODE_TYPES, TYPE_LABELS, Graph

HANDLE_NAMES = {"next": "next", "true": "Yes", "false": "No", "body": "Body", "exit": "Exit"}


def _issue(node_id, code, message, level="error"):
    return {"nodeId": node_id, "code": code, "message": message, "level": level}


def _label(node):
    return TYPE_LABELS.get(node.get("type"), "Block")


def validate_ir(ir: dict) -> dict:
    """Return {"valid": bool, "errors": [...], "warnings": [...]}."""
    issues = []
    if not isinstance(ir, dict) or not isinstance(ir.get("nodes"), list) or not isinstance(ir.get("edges"), list):
        return {"valid": False, "errors": [_issue(None, "bad_ir", "The diagram data is not valid.")], "warnings": []}

    ids = set()
    for n in ir["nodes"]:
        nid = n.get("id")
        if not nid or nid in ids:
            issues.append(_issue(nid, "dup_id", "Two blocks share the same id."))
        ids.add(nid)
        if n.get("type") not in NODE_TYPES:
            issues.append(_issue(nid, "bad_type", f"Unknown block type '{n.get('type')}'."))
    if any(i["code"] in ("bad_type", "dup_id") for i in issues):
        return _result(issues)

    for e in ir["edges"]:
        if e.get("source") not in ids or e.get("target") not in ids:
            issues.append(_issue(None, "bad_edge", "An arrow points to a block that does not exist."))
    if issues:
        return _result(issues)

    g = Graph(ir)

    # --- start / end -------------------------------------------------------
    starts, ends = g.of_type("start"), g.of_type("end")
    if len(starts) == 0:
        issues.append(_issue(None, "no_start", "Add a Start block."))
    elif len(starts) > 1:
        for s in starts:
            issues.append(_issue(s["id"], "many_start", "Only one Start block is allowed."))
    if len(ends) == 0:
        issues.append(_issue(None, "no_end", "Add an End block."))

    # --- arrows leaving each block ----------------------------------------
    for n in g.nodes.values():
        allowed = HANDLES[n["type"]]
        for handle, targets in g.out[n["id"]].items():
            if handle not in allowed:
                issues.append(_issue(n["id"], "bad_handle", f"{_label(n)} block has an arrow from an unexpected point."))
            elif len(targets) > 1:
                issues.append(_issue(n["id"], "multi_out",
                                     f"{_label(n)} block has more than one arrow leaving '{HANDLE_NAMES[handle]}'."))
        for handle in allowed:
            if not g.out[n["id"]].get(handle):
                where = "" if handle == "next" else f" on the '{HANDLE_NAMES[handle]}' side"
                issues.append(_issue(n["id"], "missing_out", f"{_label(n)} block needs an arrow leaving it{where}."))
        if n["type"] != "start" and not g.pred[n["id"]]:
            issues.append(_issue(n["id"], "no_in", f"{_label(n)} block is not connected from anywhere."))

    # --- fields & variables -----------------------------------------------
    defined = set()
    for n in g.nodes.values():
        t = n["type"]
        if t == "input":
            for part in str(n.get("variable") or "").split(","):
                if IDENT_RE.match(part.strip()):
                    defined.add(part.strip())
        elif t == "for" and IDENT_RE.match((n.get("variable") or "").strip()):
            defined.add(n["variable"].strip())
        elif t == "process" and IDENT_RE.match((n.get("variable") or "").strip()):
            defined.add(n["variable"].strip())

    for n in g.nodes.values():
        issues.extend(_check_fields(n, defined))
        note = n.get("note")
        if note is not None and not isinstance(note, str):
            issues.append(_issue(n["id"], "field", "Note: must be text."))
        elif isinstance(note, str) and len(note) > 1000:
            issues.append(_issue(n["id"], "field", "Note: is too long (at most 1000 characters)."))

    # --- connectivity -----------------------------------------------------
    if len(starts) == 1:
        reach = g.reachable_from(starts[0]["id"])
        for n in g.nodes.values():
            if n["id"] not in reach and n["type"] != "start":
                issues.append(_issue(n["id"], "unreachable", f"{_label(n)} block can never be reached from Start."))
    # every block must be able to reach an End
    can_end = set()
    stack = [e["id"] for e in ends]
    while stack:
        cur = stack.pop()
        if cur in can_end:
            continue
        can_end.add(cur)
        stack.extend(g.pred[cur])
    if ends:
        for n in g.nodes.values():
            if n["id"] not in can_end:
                issues.append(_issue(n["id"], "no_path_end", f"{_label(n)} block never leads to an End block."))

    # --- loops --------------------------------------------------------------
    loop_back = set()   # (source, loop) edges that are loop returns
    for loop in g.of_type(*LOOP_TYPES):
        body_start = g.target(loop["id"], "body")
        if not body_start:
            continue
        region, stack = set(), [body_start]
        while stack:
            cur = stack.pop()
            if cur in region or cur == loop["id"]:
                continue
            region.add(cur)
            stack.extend(g.successors(cur))
        returns = False
        for nid in region:
            for s in g.successors(nid):
                if s == loop["id"]:
                    returns = True
                    loop_back.add((nid, loop["id"]))
                elif s not in region:
                    pass
            if g.nodes[nid]["type"] == "end":
                issues.append(_issue(nid, "loop_end", "An End block cannot be inside a loop body. The body must return to the loop block."))
        if not returns:
            issues.append(_issue(loop["id"], "loop_noreturn",
                                 "The loop body never returns to the loop block. Connect the last block of the body back to the loop."))
        exit_start = g.target(loop["id"], "exit")
        if exit_start and exit_start in region:
            issues.append(_issue(loop["id"], "loop_exit_in_body", "The loop Exit arrow must lead out of the loop, not into its body."))

    # cycles other than loop returns
    if not any(i["code"] in ("missing_out",) for i in issues):
        indeg = {nid: 0 for nid in g.nodes}
        adj = {nid: [] for nid in g.nodes}
        for n in g.nodes:
            for s in g.successors(n):
                if (n, s) in loop_back:
                    continue
                adj[n].append(s)
                indeg[s] += 1
        queue = [k for k, v in indeg.items() if v == 0]
        seen = 0
        while queue:
            cur = queue.pop()
            seen += 1
            for s in adj[cur]:
                indeg[s] -= 1
                if indeg[s] == 0:
                    queue.append(s)
        if seen != len(g.nodes):
            for nid, d in indeg.items():
                if d > 0:
                    issues.append(_issue(nid, "bad_cycle",
                                         "This arrow creates a repeat that is not a loop block. Use a While or For block to repeat steps."))
                    break

    return _result(_dedupe(issues))


def _check_fields(n, defined):
    t, nid, out = n["type"], n["id"], []

    def need(label, fn):
        try:
            fn()
        except ExprError as ex:
            out.append(_issue(nid, "field", f"{label}: {ex}"))

    def undefined(used):
        for name in sorted(used):
            if name not in defined:
                out.append(_issue(nid, "undefined",
                                  f"Variable '{name}' is used but never set. Add an Input or Process block that sets it."))

    if t == "input":
        names = []
        try:
            names = parse_variable_list(n.get("variable"))
        except ExprError as ex:
            out.append(_issue(nid, "field", f"Variable: {ex}"))
        vtype = n.get("varType") or "int"
        if vtype not in INPUT_TYPES:
            out.append(_issue(nid, "field", "Input type is not valid."))
        elif len(names) > 1 and vtype not in ("int", "float", "text"):
            out.append(_issue(nid, "field", "Several names need the type Whole number, Decimal number or Text. "
                                            "A list type can only be used with one name."))
    elif t == "output":
        try:
            _, used, _ = parse_expression_list(n.get("value"), defined)
            undefined(used)
        except ExprError as ex:
            out.append(_issue(nid, "field", f"Value: {ex}"))
    elif t == "process":
        try:
            _, _, _, used_t = parse_target(n.get("variable"))
            undefined(used_t)
        except ExprError as ex:
            out.append(_issue(nid, "field", f"Variable: {ex}"))
        try:
            _, _, used, _ = parse_expression(n.get("expression"), False, defined)
            undefined(used)
        except ExprError as ex:
            out.append(_issue(nid, "field", f"Expression: {ex}"))
    elif t in ("decision", "while"):
        try:
            _, _, used, _ = parse_expression(n.get("condition"), True, defined)
            undefined(used)
        except ExprError as ex:
            out.append(_issue(nid, "field", f"Condition: {ex}"))
    elif t == "for":
        need("Variable", lambda: check_variable_name(n.get("variable")))
        for key, label in (("from", "From"), ("to", "To")):
            try:
                _, _, used, _ = parse_expression(n.get(key), False, defined)
                undefined(used)
            except ExprError as ex:
                out.append(_issue(nid, "field", f"{label}: {ex}"))
        if str(n.get("step") or "").strip():
            try:
                _, _, used, _ = parse_expression(n.get("step"), False, defined)
                undefined(used)
            except ExprError as ex:
                out.append(_issue(nid, "field", f"Step: {ex}"))
    return out


def _dedupe(issues):
    seen, res = set(), []
    for i in issues:
        key = (i["nodeId"], i["message"])
        if key not in seen:
            seen.add(key)
            res.append(i)
    return res


def _result(issues):
    errors = [i for i in issues if i["level"] == "error"]
    warnings = [i for i in issues if i["level"] != "error"]
    return {"valid": not errors, "errors": errors, "warnings": warnings}
