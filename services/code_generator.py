"""Deterministic Python code generation from a flowchart IR."""
import ast

from .expression import parse_expression, parse_expression_list, parse_target, parse_variable_list
from .flow_validator import validate_ir
from .notes import comment_lines
from .structure import StructureError, build_structure

INDENT = "    "


class GenerationError(Exception):
    def __init__(self, errors):
        super().__init__("; ".join(e["message"] for e in errors))
        self.errors = errors


def _plus_one(node):
    """Return an AST for (node + 1), simplified where easy."""
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
        return ast.Constant(node.value + 1)
    if (isinstance(node, ast.BinOp) and isinstance(node.right, ast.Constant)
            and isinstance(node.right.value, int) and not isinstance(node.right.value, bool)):
        c = node.right.value
        if isinstance(node.op, ast.Sub):
            return node.left if c == 1 else ast.BinOp(node.left, ast.Sub(), ast.Constant(c - 1)) if c > 1 \
                else ast.BinOp(node.left, ast.Add(), ast.Constant(1 - c))
        if isinstance(node.op, ast.Add):
            return ast.BinOp(node.left, ast.Add(), ast.Constant(c + 1))
    return ast.BinOp(node, ast.Add(), ast.Constant(1))


def _minus_one(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
        return ast.Constant(node.value - 1)
    return ast.BinOp(node, ast.Sub(), ast.Constant(1))


def _is_negative(tree):
    body = tree.body if isinstance(tree, ast.Expression) else tree
    if isinstance(body, ast.UnaryOp) and isinstance(body.op, ast.USub):
        return True
    return isinstance(body, ast.Constant) and isinstance(body.value, (int, float)) and body.value < 0


def _prompt(node):
    prompt = (node.get("prompt") or "").strip()
    if not prompt:
        names = parse_variable_list(node["variable"])
        if len(names) > 1:
            prompt = f"Enter {', '.join(names)} (separated by spaces or commas)"
        elif (node.get("varType") or "int") in ("list_int", "list_float"):
            prompt = f"Enter {names[0]} (values separated by spaces or commas)"
        else:
            prompt = f"Enter {names[0]}"
    if prompt[-1] not in ":?= ":
        prompt += ": "
    elif prompt[-1] != " ":
        prompt += " "
    return repr(prompt)


def _collect_variables(ir):
    names = set()
    for n in ir["nodes"]:
        if n["type"] in ("input", "for", "process"):
            for v in str(n.get("variable") or "").split(","):
                v = v.strip()
                if v.isidentifier():
                    names.add(v)
    return names


class _Emitter:
    def __init__(self, variables):
        self.variables = variables
        self.lines = []
        self.uses_math = False

    def add(self, depth, text):
        self.lines.append(INDENT * depth + text)

    def expr(self, text, is_condition=False):
        tree, src, _, um = parse_expression(text, is_condition, self.variables)
        self.uses_math |= um
        return tree, src

    def note(self, node, depth):
        """A block's note becomes comment lines right above its code."""
        for line in comment_lines(node.get("note")):
            self.add(depth, "# " + line if line else "#")

    def block(self, stmts, depth):
        for s in stmts:
            self.stmt(s, depth)
        if not any(s["kind"] != "comment" for s in stmts):
            self.add(depth, "pass")

    def stmt(self, s, depth):
        k, n = s["kind"], s["node"]
        if k == "comment":
            self.note(n, depth)
            return
        if k != "if":
            self.note(n, depth)
        if k == "input":
            names = parse_variable_list(n["variable"])
            typ, pr = n.get("varType") or "int", _prompt(n)
            if len(names) > 1:
                num_words = f"input({pr}).replace(',', ' ').replace('/', ' ').split()"
                many = {"int": f"map(int, {num_words})", "float": f"map(float, {num_words})",
                        "text": f"input({pr}).replace(',', ' ').split()"}[typ]
                self.add(depth, f"{', '.join(names)} = {many}")
                return
            var = names[0]
            rhs = {
                "int": f"int(input({pr}))",
                "float": f"float(input({pr}))",
                "text": f"input({pr})",
                "list_int": f"list(map(int, input({pr}).replace(',', ' ').replace('/', ' ').split()))",
                "list_float": f"list(map(float, input({pr}).replace(',', ' ').replace('/', ' ').split()))",
            }[typ]
            self.add(depth, f"{var} = {rhs}")
        elif k == "output":
            sources, _, um = parse_expression_list(n["value"], self.variables)
            self.uses_math |= um
            self.add(depth, f"print({', '.join(sources)})")
        elif k == "process":
            _, _, target_src, _ = parse_target(n["variable"])
            _, src = self.expr(n["expression"])
            self.add(depth, f"{target_src} = {src}")
        elif k == "if":
            self.if_chain(s, depth, first=True)
        elif k == "while":
            _, src = self.expr(n["condition"], True)
            self.add(depth, f"while {src}:")
            self.block(s["body"], depth + 1)
        elif k == "for":
            var = n["variable"].strip()
            start_tree, start_src = self.expr(n["from"])
            end_tree, _ = self.expr(n["to"])
            step_text = str(n.get("step") or "").strip()
            args = [start_src]
            if step_text:
                step_tree, step_src = self.expr(step_text)
                stop = _minus_one(end_tree.body) if _is_negative(step_tree) else _plus_one(end_tree.body)
                args += [ast.unparse(stop), step_src]
            else:
                args.append(ast.unparse(_plus_one(end_tree.body)))
            self.add(depth, f"for {var} in range({', '.join(args)}):")
            self.block(s["body"], depth + 1)

    def if_chain(self, s, depth, first):
        self.note(s["node"], depth)
        _, src = self.expr(s["node"]["condition"], True)
        self.add(depth, f"{'if' if first else 'elif'} {src}:")
        self.block(s["then"], depth + 1)
        els = s["else"]
        if len(els) == 1 and els[0]["kind"] == "if":
            self.if_chain(els[0], depth, first=False)
        elif els:
            self.add(depth, "else:")
            self.block(els, depth + 1)


def generate_python(ir: dict) -> str:
    result = validate_ir(ir)
    if not result["valid"]:
        raise GenerationError(result["errors"])
    try:
        tree = build_structure(ir)
    except StructureError as ex:
        raise GenerationError([{"nodeId": ex.node_id, "code": "structure", "message": str(ex), "level": "error"}])
    em = _Emitter(_collect_variables(ir))
    em.block(tree, 0) if tree else None
    body = em.lines or ["pass"]
    header = ["# Program generated by FlowCode"]
    if em.uses_math:
        header.append("import math")
    return "\n".join(header + [""] + body) + "\n"
