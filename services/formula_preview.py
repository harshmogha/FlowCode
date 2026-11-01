"""Formula preview: turns a typed expression into textbook maths (LaTeX), a plain-English
sentence, the Python it becomes, and helpful notes. Everything is derived from the same
safe syntax tree used for code generation, so the preview always matches the real code.
"""
import ast
import difflib
import re

from .expression import (BIG_OPS, BOX, MATH_CONSTS, ExprError, normalize, parse_expression,
                         parse_expression_list, prepare_tree, _collect_names)

BOXNAME = "BOXPLACEHOLDER"
GREEK = {"alpha", "beta", "gamma", "delta", "epsilon", "theta", "lambda", "mu", "sigma", "omega", "phi", "rho", "tau"}
CMP_LATEX = {ast.Lt: "<", ast.LtE: r"\le", ast.Gt: ">", ast.GtE: r"\ge", ast.Eq: "=", ast.NotEq: r"\ne"}
CMP_WORDS = {ast.Lt: "is less than", ast.LtE: "is at most", ast.Gt: "is greater than",
             ast.GtE: "is at least", ast.Eq: "is equal to", ast.NotEq: "is not equal to"}
TRIG = {"sin": r"\sin", "cos": r"\cos", "tan": r"\tan", "asin": r"\arcsin", "acos": r"\arccos", "atan": r"\arctan"}
TRIG_WORDS = {"sin": "the sine of", "cos": "the cosine of", "tan": "the tangent of",
              "asin": "the inverse sine of", "acos": "the inverse cosine of", "atan": "the inverse tangent of"}
SYMBOL = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/", ast.FloorDiv: "//", ast.Mod: "%", ast.Pow: "**"}


# ------------------------------------------------------------------ helpers
def _body(tree):
    return tree.body if isinstance(tree, ast.Expression) else tree


def _num(n):
    return isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)


def _is_root(n):
    """x ** (1/k) is a k-th root."""
    return (isinstance(n, ast.BinOp) and isinstance(n.op, ast.Pow) and isinstance(n.right, ast.BinOp)
            and isinstance(n.right.op, ast.Div) and isinstance(n.right.left, ast.Constant)
            and n.right.left.value == 1)


def _surface(n):
    """How tightly the printed form binds (bigger = tighter)."""
    if isinstance(n, ast.IfExp):
        return 0
    if isinstance(n, ast.BoolOp):
        return 1 if isinstance(n.op, ast.Or) else 2
    if isinstance(n, ast.UnaryOp):
        return 3 if isinstance(n.op, ast.Not) else 7
    if isinstance(n, ast.Compare):
        return 4
    if isinstance(n, ast.BinOp):
        if isinstance(n.op, (ast.Add, ast.Sub)):
            return 5
        if isinstance(n.op, (ast.Mult, ast.Mod)):
            return 6
        if isinstance(n.op, ast.Pow):
            return 9 if _is_root(n) else 8
        return 9               # division and floor division draw their own brackets
    return 9


def _complex(n):
    return isinstance(n, (ast.BinOp, ast.BoolOp, ast.Compare, ast.IfExp)) or \
        (isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not))


# ------------------------------------------------------------------ LaTeX
def _name_latex(name):
    if name == BOXNAME:
        return r"\square"
    if name == "pi":
        return r"\pi"
    if name in GREEK:
        return "\\" + name
    if len(name) == 1:
        return name
    m = re.fullmatch(r"([A-Za-z])(\d+)", name)
    if m:
        return f"{m.group(1)}_{{{m.group(2)}}}"
    return r"\mathrm{" + name.replace("_", r"\_") + "}"


def _wrap(s, need):
    return r"\left(" + s + r"\right)" if need else s


def latex(n):
    if isinstance(n, ast.Expression):
        return latex(n.body)
    if isinstance(n, ast.Constant):
        v = n.value
        if isinstance(v, bool):
            return r"\mathrm{" + ("True" if v else "False") + "}"
        if isinstance(v, str):
            return r"\text{``" + re.sub(r"([#$%&_{}\\^~])", r"\\\1", v) + r"''}"
        return repr(v)
    if isinstance(n, ast.Name):
        return _name_latex(n.id)
    if isinstance(n, ast.BinOp):
        return _binop_latex(n)
    if isinstance(n, ast.UnaryOp):
        inner = latex(n.operand)
        if isinstance(n.op, ast.Not):
            return r"\lnot\," + _wrap(inner, _surface(n.operand) < 4)
        sign = "-" if isinstance(n.op, ast.USub) else "+"
        return sign + _wrap(inner, _surface(n.operand) < 7)
    if isinstance(n, ast.BoolOp):
        word = r"\;\mathrm{and}\;" if isinstance(n.op, ast.And) else r"\;\mathrm{or}\;"
        mine = 2 if isinstance(n.op, ast.And) else 1
        return word.join(_wrap(latex(v), _surface(v) <= mine) for v in n.values)
    if isinstance(n, ast.Compare):
        out = _wrap(latex(n.left), _surface(n.left) < 5)
        for op, c in zip(n.ops, n.comparators):
            out += " " + CMP_LATEX[type(op)] + " " + _wrap(latex(c), _surface(c) < 5)
        return out
    if isinstance(n, ast.IfExp):
        return (r"\begin{cases}" + latex(n.body) + r" & \text{if } " + latex(n.test) + r" \\ " +
                latex(n.orelse) + r" & \text{otherwise}\end{cases}")
    if isinstance(n, ast.Subscript):
        return _wrap(latex(n.value), _surface(n.value) < 9) + "_{" + latex(n.slice) + "}"
    if isinstance(n, ast.Call):
        return _call_latex(n)
    return r"\text{?}"


def _binop_latex(n):
    op, l, r = n.op, n.left, n.right
    if isinstance(op, ast.Div):
        return r"\frac{" + latex(l) + "}{" + latex(r) + "}"
    if isinstance(op, ast.FloorDiv):
        return r"\left\lfloor \frac{" + latex(l) + "}{" + latex(r) + r"} \right\rfloor"
    if isinstance(op, ast.Pow):
        if _is_root(n):
            k = n.right.right
            if isinstance(k, ast.Constant) and k.value == 2:
                return r"\sqrt{" + latex(l) + "}"
            return r"\sqrt[" + latex(k) + "]{" + latex(l) + "}"
        base = latex(l)
        need = _surface(l) < 9 or (isinstance(l, ast.BinOp) and isinstance(l.op, (ast.Div, ast.FloorDiv))) or \
            (isinstance(l, ast.Constant) and isinstance(l.value, (int, float)) and l.value < 0)
        return _wrap(base, need) + "^{" + latex(r) + "}"
    if isinstance(op, ast.Add):
        return _wrap(latex(l), _surface(l) < 5) + " + " + _wrap(latex(r), _surface(r) < 5)
    if isinstance(op, ast.Sub):
        return _wrap(latex(l), _surface(l) < 5) + " - " + _wrap(latex(r), _surface(r) <= 5)
    if isinstance(op, ast.Mod):
        return _wrap(latex(l), _surface(l) < 6) + r" \bmod " + _wrap(latex(r), _surface(r) <= 6)
    # multiplication
    left = _wrap(latex(l), _surface(l) < 6)
    right = _wrap(latex(r), _surface(r) <= 6 or isinstance(r, ast.UnaryOp))
    if _num(l) and isinstance(r, (ast.Name, ast.Call)) and not _num(r):
        return left + right                                   # 2a
    return left + r" \cdot " + right


def _call_latex(n):
    name = n.func.id
    args = n.args
    if name in BIG_OPS:
        symbol = r"\sum" if name == "Sum" else r"\prod"
        i, lo, hi, body = (latex(a) for a in args)
        return f"{symbol}_{{{i}={lo}}}^{{{hi}}} " + _wrap(body, _surface(args[3]) < 6)
    a = [latex(x) for x in args]
    one = a[0] if a else ""
    if name == "sqrt":
        return r"\sqrt{" + one + "}"
    if name == "abs":
        return r"\left|" + one + r"\right|"
    if name == "floor":
        return r"\left\lfloor " + one + r" \right\rfloor"
    if name == "ceil":
        return r"\left\lceil " + one + r" \right\rceil"
    if name == "factorial":
        return _wrap(one, _surface(args[0]) < 9) + "!"
    if name in TRIG:
        return TRIG[name] + r"\left(" + one + r"\right)"
    if name == "log" and len(a) == 2:
        return r"\log_{" + a[1] + r"}\left(" + one + r"\right)"
    if name == "log":
        return r"\ln\left(" + one + r"\right)"
    if name == "log10":
        return r"\log_{10}\left(" + one + r"\right)"
    if name == "exp":
        return "e^{" + one + "}"
    if name in ("min", "max", "gcd"):
        return "\\" + name + r"\left(" + ", ".join(a) + r"\right)"
    if name == "pow" and len(a) == 2:
        return _wrap(a[0], _surface(args[0]) < 9) + "^{" + a[1] + "}"
    return r"\mathrm{" + name + r"}\left(" + ", ".join(a) + r"\right)"


# ------------------------------------------------------------------ English
def _sub(n):
    text = english(n)
    return "(" + text + ")" if _complex(n) else text


def _chain(n, parent_group):
    """Operand of a + - or * chain: no brackets when it continues the same chain."""
    group = None
    if isinstance(n, ast.BinOp):
        if isinstance(n.op, (ast.Add, ast.Sub)):
            group = "add"
        elif isinstance(n.op, ast.Mult):
            group = "mul"
    return english(n) if group == parent_group else _sub(n)


def _ordinal(k):
    if 10 <= k % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(k % 10, "th")
    return f"{k}{suffix}"


def english(n):
    if isinstance(n, ast.Expression):
        return english(n.body)
    if isinstance(n, ast.Constant):
        v = n.value
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, str):
            return f'the text "{v}"'
        return repr(v)
    if isinstance(n, ast.Name):
        if n.id == BOXNAME:
            return "an empty box"
        return {"pi": "pi", "e": "e"}.get(n.id, n.id) if n.id in MATH_CONSTS else n.id
    if isinstance(n, ast.BinOp):
        op, l, r = n.op, n.left, n.right
        if isinstance(op, ast.Add):
            return f"{_chain(l, 'add')} plus {_sub(r)}"
        if isinstance(op, ast.Sub):
            return f"{_chain(l, 'add')} minus {_sub(r)}"
        if isinstance(op, ast.Mult):
            return f"{_chain(l, 'mul')} times {_sub(r)}"
        if isinstance(op, ast.Div):
            return f"{_sub(l)} divided by {_sub(r)}"
        if isinstance(op, ast.FloorDiv):
            return f"the whole-number part of {_sub(l)} divided by {_sub(r)}"
        if isinstance(op, ast.Mod):
            return f"the remainder of {_sub(l)} divided by {_sub(r)}"
        if _is_root(n):
            k = n.right.right
            if isinstance(k, ast.Constant) and k.value == 2:
                return f"the square root of {_sub(l)}"
            if isinstance(k, ast.Constant) and k.value == 3:
                return f"the cube root of {_sub(l)}"
            if isinstance(k, ast.Constant) and isinstance(k.value, int):
                return f"the {_ordinal(k.value)} root of {_sub(l)}"
            return f"the root of degree {_sub(k)} of {_sub(l)}"
        if isinstance(r, ast.Constant) and r.value == 2:
            return f"{_sub(l)} squared"
        if isinstance(r, ast.Constant) and r.value == 3:
            return f"{_sub(l)} cubed"
        return f"{_sub(l)} to the power of {_sub(r)}"
    if isinstance(n, ast.UnaryOp):
        if isinstance(n.op, ast.Not):
            return f"not {_sub(n.operand)}"
        return ("negative " if isinstance(n.op, ast.USub) else "") + _sub(n.operand)
    if isinstance(n, ast.BoolOp):
        word = " and " if isinstance(n.op, ast.And) else " or "
        return word.join(_sub(v) if _complex(v) and not isinstance(v, ast.Compare) else english(v) for v in n.values)
    if isinstance(n, ast.Compare):
        out = _sub(n.left) if not isinstance(n.left, ast.Compare) else english(n.left)
        for op, c in zip(n.ops, n.comparators):
            out += f" {CMP_WORDS[type(op)]} {_sub(c)}"
        return out
    if isinstance(n, ast.IfExp):
        return f"{english(n.body)} if {english(n.test)}, otherwise {english(n.orelse)}"
    if isinstance(n, ast.Subscript):
        return f"item {english(n.slice)} of {_sub(n.value)}"
    if isinstance(n, ast.Call):
        name, args = n.func.id, n.args
        if name in BIG_OPS:
            what = "sum" if name == "Sum" else "product"
            i, lo, hi, body = args
            return f"the {what} of {_sub(body)} for {english(i)} from {_sub(lo)} to {_sub(hi)}"
        one = _sub(args[0]) if args else ""
        simple = {"sqrt": "the square root of", "abs": "the absolute value of", "floor": "round down",
                  "ceil": "round up", "factorial": "the factorial of", "log10": "the base-10 logarithm of",
                  "exp": "e to the power of", "len": "the length of", "int": "the whole number of",
                  "float": "the decimal number of", "str": "the text of", "round": "round"}
        if name in TRIG_WORDS:
            return f"{TRIG_WORDS[name]} {one}"
        if name == "log":
            return f"the logarithm of {one} with base {_sub(args[1])}" if len(args) == 2 else f"the natural logarithm of {one}"
        if name in simple:
            return f"{simple[name]} {one}"
        if name in ("min", "max", "gcd"):
            words = {"min": "the smallest of", "max": "the largest of", "gcd": "the greatest common divisor of"}[name]
            return f"{words} " + ", ".join(_sub(a) for a in args)
        if name == "pow" and len(args) == 2:
            return f"{_sub(args[0])} to the power of {_sub(args[1])}"
        return f"{name} of " + ", ".join(_sub(a) for a in args)
    return "?"


# ------------------------------------------------------------------ extras
def ordered(n, top=True):
    """The formula with brackets around every operation, to show the order of calculation."""
    if isinstance(n, ast.Expression):
        return ordered(n.body, top)
    if isinstance(n, ast.BinOp):
        text = f"{ordered(n.left, False)} {SYMBOL[type(n.op)]} {ordered(n.right, False)}"
        return text if top else f"({text})"
    if isinstance(n, ast.BoolOp):
        w = " and " if isinstance(n.op, ast.And) else " or "
        text = w.join(ordered(v, False) for v in n.values)
        return text if top else f"({text})"
    if isinstance(n, ast.Compare):
        sym = {ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">=", ast.Eq: "==", ast.NotEq: "!="}
        text = ordered(n.left, False)
        for op, c in zip(n.ops, n.comparators):
            text += f" {sym[type(op)]} {ordered(c, False)}"
        return text if top else f"({text})"
    if isinstance(n, ast.UnaryOp):
        s = "not " if isinstance(n.op, ast.Not) else ("-" if isinstance(n.op, ast.USub) else "+")
        return s + ordered(n.operand, False)
    if isinstance(n, ast.Call):
        return n.func.id + "(" + ", ".join(ordered(a, True) for a in n.args) + ")"
    if isinstance(n, ast.Subscript):
        return ordered(n.value, False) + "[" + ordered(n.slice, True) + "]"
    if isinstance(n, ast.Constant):
        return repr(n.value) if isinstance(n.value, str) else str(n.value)
    if isinstance(n, ast.Name):
        return n.id
    return ast.unparse(n)


def result_type(tree):
    t = _body(tree)
    if isinstance(t, (ast.Compare, ast.BoolOp)) or (isinstance(t, ast.UnaryOp) and isinstance(t.op, ast.Not)):
        return "true or false"
    if isinstance(t, ast.Constant) and isinstance(t.value, str):
        return "text"
    decimal = False
    for n in ast.walk(t):
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div):
            decimal = True
        elif isinstance(n, ast.Constant) and isinstance(n.value, float):
            decimal = True
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in (
                "sqrt", "sin", "cos", "tan", "asin", "acos", "atan", "log", "log10", "exp", "float"):
            decimal = True
        elif isinstance(n, ast.Name) and n.id in MATH_CONSTS:
            decimal = True
    if decimal:
        return "decimal number"
    if isinstance(t, (ast.Name, ast.Subscript)):
        return "a stored value"
    return "number (whole if every input is whole)"


def _notes(tree, variables, used):
    notes = []
    t = _body(tree)
    for n in ast.walk(t):
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Div, ast.FloorDiv, ast.Mod)) and \
                isinstance(n.right, ast.Constant) and n.right.value == 0:
            notes.append({"level": "error", "text": "Dividing by 0 will make the program stop."})
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.args and _num(n.args[0]):
            v = n.args[0].value
            if n.func.id == "sqrt" and v < 0:
                notes.append({"level": "error", "text": "The square root of a negative number is not allowed."})
            if n.func.id in ("log", "log10") and v <= 0:
                notes.append({"level": "error", "text": "A logarithm needs a number greater than 0."})
    # undefined variables with "did you mean"
    known = set(variables)
    for name in sorted(used):
        if name == BOXNAME or name in known:
            continue
        close = difflib.get_close_matches(name, known, n=1, cutoff=0.6)
        hint = f" Did you mean '{close[0]}'?" if close else ""
        notes.append({"level": "warn", "text": f"'{name}' is not set anywhere yet.{hint}"})
    # classic precedence slip: start + end / 2
    if isinstance(t, ast.BinOp) and isinstance(t.op, (ast.Add, ast.Sub)) and isinstance(t.right, ast.BinOp) and \
            isinstance(t.right.op, ast.Div) and isinstance(t.left, (ast.Name, ast.Subscript)):
        a, b = ordered(t.left), ordered(t.right.left, False)
        notes.append({"level": "hint", "text":
                      f"Division happens first: this is {a} {SYMBOL[type(t.op)]} ({ordered(t.right)}). "
                      f"For the average of {a} and {b}, write ({a} + {b}) / 2."})
    return notes


# ------------------------------------------------------------------ public API
def _parse_items(text, kind):
    """Return the syntax trees to describe (several for a PRINT list)."""
    if kind == "list":
        raw = text.replace(BOX, BOXNAME)
        norm = normalize(raw)
        try:
            tree = ast.parse("[" + norm + "]", mode="eval")
        except SyntaxError:
            raise ExprError(f"Could not understand '{text.strip()}'. Text must be inside quotes.")
        if not isinstance(tree.body, ast.List) or not tree.body.elts:
            raise ExprError("Could not understand this value.")
        from .expression import _check_node
        for el in tree.body.elts:
            _check_node(el)
        return [ast.Expression(body=el) for el in tree.body.elts]
    return [prepare_tree(text, kind == "condition", allow_boxes=True)]


def preview(text, kind="expression", variables=()):
    text = "" if text is None else str(text)
    if kind == "note":
        return preview_note(text)
    if not text.strip():
        return {"ok": True, "empty": True}
    try:
        trees = _parse_items(text, kind)
    except ExprError as ex:
        return {"ok": False, "error": str(ex)}
    incomplete = BOX in text
    used = set()
    for tr in trees:
        used |= _collect_names(tr, set(variables))
    first = trees[0]
    result = {
        "ok": True,
        "latex": r",\;\; ".join(latex(t) for t in trees),
        "reading": "; ".join(english(t) for t in trees),
        "type": result_type(first) if len(trees) == 1 else "a list of values",
        "ordered": ordered(first) if len(trees) == 1 else None,
        "incomplete": incomplete,
        "python": None,
        "notes": [],
    }
    if incomplete:
        result["ordered"] = None
        result["notes"].append({"level": "hint", "text": "Type over the empty boxes. Press Tab to jump to the next box."})
        return result
    try:
        if kind == "list":
            sources, _, _ = parse_expression_list(text, variables)
            result["python"] = "print(" + ", ".join(sources) + ")"
        else:
            _, src, _, _ = parse_expression(text, kind == "condition", variables)
            result["python"] = src
    except ExprError as ex:
        result["notes"].append({"level": "error", "text": str(ex)})
    result["notes"] += _notes(first, variables, used) if len(trees) == 1 else \
        [n for tr in trees for n in _notes(tr, variables, used)]
    if "(" in text or "[" in text or result["ordered"] == normalize(text).strip():
        result["ordered"] = None                       # brackets already show the order, or nothing new to say
    return result


# ------------------------------------------------------------------ notes
_EQUATION = re.compile(r"(?<![=!<>:])=(?!=)")


def _note_formula(chunk):
    raw = chunk.strip()
    if not raw:
        return {"error": "There is nothing between the two $ signs.", "raw": ""}
    try:
        m = _EQUATION.search(raw)
        if m and raw[:m.start()].strip() and raw[m.end():].strip():
            left = prepare_tree(raw[:m.start()], False, allow_boxes=True)
            right = prepare_tree(raw[m.end():], False, allow_boxes=True)
            return {"latex": latex(left) + " = " + latex(right), "reading": f"{english(left)} equals {english(right)}"}
        tree = prepare_tree(raw, False, allow_boxes=True)
        return {"latex": latex(tree), "reading": english(tree)}
    except ExprError as ex:
        return {"error": str(ex), "raw": raw}


def preview_note(text):
    """Split a note into plain text and $formula$ parts, so the page can typeset the formulas."""
    from .notes import comment_lines
    text = "" if text is None else str(text)
    if not text.strip():
        return {"ok": True, "empty": True}
    parts = text.split("$")
    closed = len(parts) % 2 == 1                     # an odd number of $ signs leaves the last one unclosed
    segments, notes = [], []
    for i, chunk in enumerate(parts):
        is_formula = i % 2 == 1 and (closed or i < len(parts) - 1)
        if is_formula:
            seg = _note_formula(chunk)
            segments.append(seg)
            if "reading" in seg:
                notes.append({"level": "hint", "text": "Formula reads: " + seg["reading"]})
            else:
                notes.append({"level": "warn", "text": f"Formula '{seg.get('raw', '')}': {seg['error']}"})
        else:
            if i % 2 == 1:                           # unclosed $
                chunk = "$" + chunk
                notes.append({"level": "warn", "text": "A $ sign is not closed. Put formulas between two $ signs."})
            if chunk:
                segments.append({"text": chunk})
    return {"ok": True, "kind": "note", "segments": segments, "notes": notes,
            "comment": ["# " + line if line else "#" for line in comment_lines(text)]}
