"""Runs Python code in a separate process with a time limit.

This is a convenience for a local, single-user learning tool. It is NOT a
hardened sandbox: it blocks obviously dangerous constructs, runs in an
isolated interpreter (-I) inside a temporary folder, and enforces a timeout
and an output size limit.

`run_python` runs a program to the end with pre-typed input (used by tests).
The console in the web page uses `services/interactive.py`, which runs the same
runner in "interactive" mode so the program can pause and ask for a value.
"""
import ast
import os
import subprocess
import sys
import tempfile

TIMEOUT_SECONDS = 5
MAX_OUTPUT = 20000

BLOCKED_NAMES = {
    "open", "exec", "eval", "compile", "__import__", "globals", "locals", "vars", "dir",
    "getattr", "setattr", "delattr", "breakpoint", "exit", "quit", "help", "memoryview",
}

# The program the child process runs: it executes the user's code with a replacement input().
# argv[1] = path of the user's program, argv[2] = "interactive" (optional).
RUNNER = r'''
import sys, builtins, re

interactive = len(sys.argv) > 2 and sys.argv[2] == "interactive"
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", newline="\n")      # no \r\n on Windows
    except Exception:
        pass
try:
    sys.stdin.reconfigure(encoding="utf-8")
except Exception:
    pass

MARK = "\x00WAIT\x00"          # tells the page "I am waiting for a value now"
src = open(sys.argv[1], encoding="utf-8").read()


def _inp(prompt=""):
    if interactive:
        sys.stdout.write(str(prompt) + MARK)
        sys.stdout.flush()
        line = sys.stdin.readline()
        if line == "":
            raise EOFError("The program was waiting for a value, but the run was stopped.")
        return line.rstrip("\r\n")
    line = sys.stdin.readline()
    if line == "":
        raise EOFError("The program asked for more input than you provided.")
    line = line.rstrip("\r\n")
    sys.stdout.write(str(prompt) + line + "\n")
    sys.stdout.flush()
    return line


builtins.input = _inp
try:
    code = compile(src, "<program>", "exec")
    exec(code, {"__name__": "__main__"})
except SystemExit:
    pass
except BaseException as ex:
    import traceback
    lineno = None
    for fr in traceback.extract_tb(ex.__traceback__):
        if fr.filename == "<program>":
            lineno = fr.lineno
    where = f" on line {lineno}" if lineno else ""
    msg = str(ex)
    help_text = None
    if isinstance(ex, ValueError):
        m = re.match(r"invalid literal for int\(\) with base 10: (.+)", msg)
        if m:
            help_text = ("The program expected a whole number but got " + m.group(1) + ". Type only the number, for example 5. "
                         "To enter several values on one line, set the Input block's variable name to a, b and type them like 3 4.")
        m = re.match(r"could not convert string to float: (.+)", msg)
        if m:
            help_text = "The program expected a number but got " + m.group(1) + ". Type only the number, for example 2.5."
        m = re.match(r"not enough values to unpack \(expected (\d+), got (\d+)\)", msg)
        if m:
            help_text = ("The program wanted " + m.group(1) + " values on one line but got " + m.group(2) +
                         ". Type them on the same line separated by a space, for example 3 4.")
        m = re.match(r"too many values to unpack \(expected (\d+)", msg)
        if m:
            help_text = ("The program wanted " + m.group(1) + " values on one line but got more. "
                         "Type exactly " + m.group(1) + " values, or add more names to the Input block.")
    elif isinstance(ex, ZeroDivisionError):
        help_text = "The program divided by zero. Check the values you typed and the formula."
    elif isinstance(ex, IndexError):
        help_text = "The program used a list position that does not exist. Check the loop limits and the list length."
    sys.stdout.flush()
    if help_text:
        sys.stderr.write("Error" + where + ": " + help_text + "\n(technical detail: " + type(ex).__name__ + ": " + msg + ")\n")
    else:
        sys.stderr.write(f"Error{where}: {type(ex).__name__}: {ex}\n")
    sys.exit(1)
'''


def check_python_safe(code: str):
    """Return an error message if the code uses blocked features, else None."""
    try:
        tree = ast.parse(code)
    except SyntaxError as ex:
        return f"Syntax error on line {ex.lineno}: {ex.msg}"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name != "math":
                    return f"Importing '{a.name}' is not allowed. Only 'math' can be imported."
        elif isinstance(node, ast.ImportFrom):
            if node.module != "math":
                return f"Importing from '{node.module}' is not allowed. Only 'math' can be imported."
        elif isinstance(node, ast.Name) and node.id in BLOCKED_NAMES:
            return f"'{node.id}' is not allowed in this tool."
        elif isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            return "Names starting with an underscore are not allowed."
    return None


def child_env():
    return {"PYTHONIOENCODING": "utf-8", "SYSTEMROOT": os.environ.get("SYSTEMROOT", "")}


def write_program(tmp: str, code: str):
    """Write the user's program and the runner into `tmp`; returns their paths."""
    prog = os.path.join(tmp, "program.py")
    runner = os.path.join(tmp, "runner.py")
    with open(prog, "w", encoding="utf-8") as f:
        f.write(code)
    with open(runner, "w", encoding="utf-8") as f:
        f.write(RUNNER)
    return prog, runner


def run_python(code: str, stdin_text: str = ""):
    problem = check_python_safe(code)
    if problem:
        return {"ok": False, "stdout": "", "stderr": problem, "timedOut": False}
    with tempfile.TemporaryDirectory() as tmp:
        prog, runner = write_program(tmp, code)
        try:
            proc = subprocess.run(
                [sys.executable, "-I", runner, prog],
                input=stdin_text, capture_output=True, text=True, encoding="utf-8",
                timeout=TIMEOUT_SECONDS, cwd=tmp, env=child_env(),
            )
        except subprocess.TimeoutExpired as ex:
            out = (ex.stdout or b"")
            if isinstance(out, bytes):
                out = out.decode("utf-8", "replace")
            return {"ok": False, "stdout": out[:MAX_OUTPUT], "timedOut": True,
                    "stderr": f"Stopped: the program ran longer than {TIMEOUT_SECONDS} seconds (maybe an endless loop)."}
        return {
            "ok": proc.returncode == 0,
            "stdout": proc.stdout[:MAX_OUTPUT],
            "stderr": proc.stderr[:MAX_OUTPUT],
            "timedOut": False,
        }
