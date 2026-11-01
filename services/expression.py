"""Safe parsing of user-written expressions.

Users type friendly text such as ``n mod 2 = 0`` or ``(low + high) div 2``.
This module normalises that text, parses it with Python's ``ast`` module,
accepts only a small whitelist of syntax, and returns Python source.
Nothing is ever passed to ``eval``/``exec``.
"""
import ast
import keyword
import re

BUILTIN_FUNCS = {"abs", "min", "max", "round", "int", "float", "str", "len", "pow", "sum"}
MATH_FUNCS = {
    "sqrt", "floor", "ceil", "sin", "cos", "tan", "asin", "acos", "atan",
    "log", "log10", "exp", "factorial", "gcd",
}
MATH_CONSTS = {"pi", "e"}
ALLOWED_FUNCS = BUILTIN_FUNCS | MATH_FUNCS
# Sum(i, 1, n, i^2) = sigma notation, Prod(i, 1, n, i) = pi notation
BIG_OPS = {"Sum", "Prod"}
BOX = "\u25a1"          # the empty box inserted by the formula templates

# Variable names users may not use (Python keywords, builtins and helpers).
RESERVED_NAMES = (
    set(keyword.kwlist)
    | BUILTIN_FUNCS
    | MATH_FUNCS
    | {"print", "input", "list", "range", "math", "open", "exec", "eval", "set", "dict", "tuple", "map"}
    | BIG_OPS
)

ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)
ALLOWED_UNARY = (ast.USub, ast.UAdd, ast.Not)
ALLOWED_CMP = (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)

IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_STRING_RE = re.compile(r"""("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')""")
_IMPLICIT_MUL = re.compile(r"(?<![\w.])\d+(?:\.\d+)?\s*[A-Za-z_(]")


def _syntax_message(original: str, normalized: str) -> str:
    msg = f"Could not understand '{str(original).strip()}'. Check brackets and operators."
    if _IMPLICIT_MUL.search(_STRING_RE.sub('""', normalized)):
        msg += " If you meant multiplication, write * (for example 4*a*c, not 4ac)."
    return msg


class ExprError(Exception):
    """Raised when an expression cannot be accepted."""


def _normalize_segment(seg: str, is_condition: bool) -> str:
    seg = (seg.replace("\u00d7", "*").replace("\u00f7", "/")
              .replace("\u2264", "<=").replace("\u2265", ">=").replace("\u2260", "!=")
              .replace("\u2212", "-").replace("\u221a", "sqrt"))
    seg = seg.replace("<>", "!=").replace("^", "**")
    seg = re.sub(r"\bmod\b", "%", seg, flags=re.I)
    seg = re.sub(r"\bdiv\b", "//", seg, flags=re.I)
    seg = re.sub(r"\band\b", "and", seg, flags=re.I)
    seg = re.sub(r"\bor\b", "or", seg, flags=re.I)
    seg = re.sub(r"\bnot\b", "not", seg, flags=re.I)
    seg = re.sub(r"\btrue\b", "True", seg, flags=re.I)
    seg = re.sub(r"\bfalse\b", "False", seg, flags=re.I)
    if is_condition:
        # A single "=" in a condition means "is equal to".
        seg = re.sub(r"(?<![=!<>])=(?!=)", "==", seg)
    return seg


def normalize(text: str, is_condition: bool = False) -> str:
    parts = _STRING_RE.split(text.strip())
    out = []
    for i, part in enumerate(parts):
        out.append(part if i % 2 == 1 else _normalize_segment(part, is_condition))
    return "".join(out)


def _check_node(node: ast.AST) -> None:
    if isinstance(node, ast.Expression):
        _check_node(node.body)
    elif isinstance(node, ast.BoolOp):
        for v in node.values:
            _check_node(v)
    elif isinstance(node, ast.BinOp):
        if not isinstance(node.op, ALLOWED_BINOPS):
            raise ExprError("This operator is not supported.")
        _check_node(node.left)
        _check_node(node.right)
    elif isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, ALLOWED_UNARY):
            raise ExprError("This operator is not supported.")
        _check_node(node.operand)
    elif isinstance(node, ast.Compare):
        if not all(isinstance(op, ALLOWED_CMP) for op in node.ops):
            raise ExprError("This comparison is not supported.")
        _check_node(node.left)
        for c in node.comparators:
            _check_node(c)
    elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in BIG_OPS:
        name = node.func.id
        if len(node.args) != 4 or node.keywords:
            raise ExprError(f"{name} needs four parts: {name}(i, first, last, formula). Example: {name}(i, 1, n, i^2)")
        counter, lo, hi, body = node.args
        if not isinstance(counter, ast.Name) or counter.id in RESERVED_NAMES:
            raise ExprError(f"The first part of {name} must be a counter name such as i.")
        for part in (lo, hi, body):
            _check_node(part)
    elif isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ExprError("Something is missing before the bracket. To multiply, write * , for example 2 * (n + 1).")
        if node.func.id not in ALLOWED_FUNCS:
            raise ExprError(f"'{node.func.id}' is not a known function. To multiply, write {node.func.id} * (...).")
        if node.keywords:
            raise ExprError("Named arguments are not supported.")
        for a in node.args:
            _check_node(a)
    elif isinstance(node, ast.Constant):
        if not isinstance(node.value, (int, float, str, bool)):
            raise ExprError("This value is not supported.")
    elif isinstance(node, ast.Name):
        if node.id.startswith("__"):
            raise ExprError("This name is not allowed.")
    elif isinstance(node, ast.Subscript):
        if isinstance(node.slice, (ast.Slice, ast.Tuple)):
            raise ExprError("Only a single index like a[i] is supported.")
        _check_node(node.value)
        _check_node(node.slice)
    elif isinstance(node, ast.IfExp):
        _check_node(node.test)
        _check_node(node.body)
        _check_node(node.orelse)
    else:
        raise ExprError("This kind of expression is not supported.")


class _MathPrefixer(ast.NodeTransformer):
    """Rewrites sqrt(x) -> math.sqrt(x), pi -> math.pi and Sum/Prod into generator expressions."""

    def __init__(self, variables):
        self.variables = set(variables)
        self.bound = set()
        self.used_math = False

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id in BIG_OPS and len(node.args) == 4:
            counter, lo, hi, body = node.args
            lo, hi = self.visit(lo), self.visit(hi)
            self.bound.add(counter.id)
            try:
                body = self.visit(body)
            finally:
                self.bound.discard(counter.id)
            stop = ast.BinOp(left=hi, op=ast.Add(), right=ast.Constant(1))
            gen = ast.GeneratorExp(
                elt=body,
                generators=[ast.comprehension(
                    target=ast.Name(id=counter.id, ctx=ast.Store()),
                    iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[lo, stop], keywords=[]),
                    ifs=[], is_async=0)])
            if node.func.id == "Sum":
                func = ast.Name(id="sum", ctx=ast.Load())
            else:
                self.used_math = True
                func = ast.Attribute(value=ast.Name(id="math", ctx=ast.Load()), attr="prod", ctx=ast.Load())
            return ast.Call(func=func, args=[gen], keywords=[])
        self.generic_visit(node)
        if isinstance(node.func, ast.Name) and node.func.id in MATH_FUNCS:
            self.used_math = True
            node.func = ast.Attribute(value=ast.Name(id="math", ctx=ast.Load()),
                                      attr=node.func.id, ctx=ast.Load())
        return node

    def visit_Name(self, node):
        if node.id in MATH_CONSTS and node.id not in self.variables and node.id not in self.bound:
            self.used_math = True
            return ast.Attribute(value=ast.Name(id="math", ctx=ast.Load()),
                                 attr=node.id, ctx=ast.Load())
        return node


def _collect_names(tree: ast.AST, variables) -> set:
    names = set()

    def walk(n, bound):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
            if n.func.id in BIG_OPS and len(n.args) == 4 and isinstance(n.args[0], ast.Name):
                walk(n.args[1], bound)
                walk(n.args[2], bound)
                walk(n.args[3], bound | {n.args[0].id})
                return
            for a in n.args:
                walk(a, bound)
            return
        if isinstance(n, ast.Name):
            if n.id in bound or n.id in ("True", "False"):
                return
            if n.id in MATH_CONSTS and n.id not in variables:
                return
            names.add(n.id)
            return
        for child in ast.iter_child_nodes(n):
            walk(child, bound)

    walk(tree, frozenset())
    return names


def prepare_tree(text: str, is_condition: bool = False, allow_boxes: bool = False):
    """Parse and validate without rewriting (used by the formula preview)."""
    text = "" if text is None else str(text)
    if allow_boxes:
        text = text.replace(BOX, "BOXPLACEHOLDER")
    elif BOX in text:
        raise ExprError("Fill in the empty boxes first.")
    if not text.strip():
        raise ExprError("This field is empty.")
    norm = normalize(text, is_condition)
    try:
        tree = ast.parse(norm, mode="eval")
    except SyntaxError:
        raise ExprError(_syntax_message(text, norm))
    _check_node(tree)
    return tree


def parse_expression(text: str, is_condition: bool = False, variables=()):
    """Return (tree, python_source, used_names, uses_math). Raises ExprError."""
    if text is not None and BOX in str(text):
        raise ExprError("Fill in the empty boxes first.")
    if text is None or not str(text).strip():
        raise ExprError("This field is empty.")
    norm = normalize(str(text), is_condition)
    try:
        tree = ast.parse(norm, mode="eval")
    except SyntaxError:
        raise ExprError(_syntax_message(text, norm))
    _check_node(tree)
    used = _collect_names(tree, set(variables))
    prefixer = _MathPrefixer(variables)
    tree = prefixer.visit(tree)
    ast.fix_missing_locations(tree)
    return tree, ast.unparse(tree), used, prefixer.used_math


def parse_expression_list(text: str, variables=()):
    """Parse 'a, b, "text"' into a list of source strings (for PRINT)."""
    if text is not None and BOX in str(text):
        raise ExprError("Fill in the empty boxes first.")
    if text is None or not str(text).strip():
        raise ExprError("This field is empty.")
    norm = normalize(str(text))
    try:
        tree = ast.parse("[" + norm + "]", mode="eval")
    except SyntaxError:
        raise ExprError(f"Could not understand '{str(text).strip()}'. Text must be inside quotes.")
    if not isinstance(tree.body, ast.List):
        raise ExprError("Could not understand this value.")
    sources, used, uses_math = [], set(), False
    prefixer = _MathPrefixer(variables)
    for el in tree.body.elts:
        if isinstance(el, ast.Starred):
            raise ExprError("This kind of expression is not supported.")
        _check_node(el)
        used |= _collect_names(el, set(variables))
        el = prefixer.visit(el)
        ast.fix_missing_locations(el)
        sources.append(ast.unparse(el))
    return sources, used, prefixer.used_math


def parse_target(text: str):
    """A process target is a name `x` or an element `a[i]`. Returns (base, tree, src, used_names)."""
    if text is not None and BOX in str(text):
        raise ExprError("Fill in the empty boxes first.")
    if text is None or not str(text).strip():
        raise ExprError("Variable name is empty.")
    raw = str(text).strip()
    if IDENT_RE.match(raw):
        if raw in RESERVED_NAMES:
            raise ExprError(f"'{raw}' is a reserved word. Choose another name.")
        return raw, None, raw, set()
    try:
        tree = ast.parse(raw, mode="eval")
    except SyntaxError:
        raise ExprError(f"'{raw}' is not a valid variable name.")
    body = tree.body
    if isinstance(body, ast.Subscript) and isinstance(body.value, ast.Name):
        _check_node(tree)
        used = _collect_names(tree, set())
        return body.value.id, tree, ast.unparse(tree), used
    raise ExprError(f"'{raw}' is not a valid variable name. Use a name like x or an item like a[i].")


def parse_variable_list(text) -> list:
    """'a, b' -> ['a', 'b'] (every name checked). Used by Input blocks that read several values."""
    raw = "" if text is None else str(text)
    if BOX in raw:
        raise ExprError("Fill in the empty boxes first.")
    names = [p.strip() for p in raw.split(",")]
    if not raw.strip() or any(not p for p in names):
        raise ExprError("Variable name is empty. For several values write names separated by commas, e.g. a, b")
    for name in names:
        check_variable_name(name)
    if len(set(names)) != len(names):
        raise ExprError("The same name is used twice.")
    if len(names) > 10:
        raise ExprError("An Input block can read at most 10 values.")
    return names


def check_variable_name(name: str) -> None:
    name = (name or "").strip()
    if not name:
        raise ExprError("Variable name is empty.")
    if not IDENT_RE.match(name):
        raise ExprError(f"'{name}' is not a valid name. Use letters, digits and _ and start with a letter.")
    if name in RESERVED_NAMES:
        raise ExprError(f"'{name}' is a reserved word. Choose another name.")
