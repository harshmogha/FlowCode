import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.algorithm_text import describe_steps, parse_algorithm, print_algorithm
from services.code_generator import GenerationError, generate_python
from services.examples import EXAMPLES
from services.executor import check_python_safe, run_python
from services.flow_validator import validate_ir


def ir_of(text):
    res = parse_algorithm(text)
    assert res["ok"], res["errors"]
    return res["ir"]


@pytest.mark.parametrize("example", EXAMPLES, ids=[e["name"] for e in EXAMPLES])
def test_examples_validate_and_generate(example):
    ir = ir_of(example["text"])
    assert validate_ir(ir)["valid"], validate_ir(ir)["errors"]
    code = generate_python(ir)
    compile(code, "<gen>", "exec")
    # round trip: flowchart -> text -> flowchart gives same code
    again = generate_python(ir_of(print_algorithm(ir)))
    assert again == code
    assert describe_steps(ir)[0]["text"] == "Start"


@pytest.mark.parametrize("name,stdin,expected", [
    ("Even or odd", "7\n", "Odd"),
    ("Even or odd", "10\n", "Even"),
    ("Sum of 1 to n", "10\n", "Sum is 55"),
    ("Factorial (while loop)", "5\n", "Factorial is 120"),
    ("Quadratic equation", "1\n-3\n2\n", "Roots are 2.0 1.0"),
    ("Quadratic equation", "1\n0\n1\n", "No real roots"),
    ("Bubble sort", "5 2 9 1 3\n", "Sorted: [1, 2, 3, 5, 9]"),
    ("Binary search", "1 3 5 7 9\n7\n", "Found at index 3"),
    ("Binary search", "1 3 5 7 9\n4\n", "Not found"),
])
def test_examples_run(name, stdin, expected):
    text = next(e["text"] for e in EXAMPLES if e["name"] == name)
    result = run_python(generate_python(ir_of(text)), stdin)
    assert result["ok"], result
    assert expected in result["stdout"]


def test_even_odd_code_shape():
    code = generate_python(ir_of(EXAMPLES[0]["text"]))
    assert "n = int(input('Enter a number: '))" in code
    assert "if n % 2 == 0:" in code
    assert "else:" in code


def test_for_loop_range_simplified():
    code = generate_python(ir_of(EXAMPLES[4]["text"]))
    assert "range(0, n - 1)" in code
    assert "range(0, n - i - 1)" in code


def test_validator_catches_problems():
    ir = ir_of(EXAMPLES[0]["text"])
    # remove an edge leaving the decision's "No" side
    ir["edges"] = [e for e in ir["edges"] if e.get("sourceHandle") != "false"]
    res = validate_ir(ir)
    assert not res["valid"]
    assert any("No" in e["message"] for e in res["errors"])


def test_validator_undefined_variable():
    ir = ir_of('START\nPRINT x\nEND\n')
    errors = validate_ir(ir)["errors"]
    assert any("never set" in e["message"] for e in errors)


def test_generation_refuses_invalid():
    ir = ir_of('START\nPRINT x\nEND\n')
    with pytest.raises(GenerationError):
        generate_python(ir)


def test_parser_errors_have_line_numbers():
    res = parse_algorithm("START\nIF x > 1 THEN\nPRINT 1\nEND\n")
    assert not res["ok"] and res["errors"][0]["line"] == 2
    res = parse_algorithm("START\nSET x = 3 +\nEND\n")
    assert not res["ok"] and res["errors"][0]["line"] == 2


@pytest.mark.parametrize("bad", [
    "__import__('os').system('dir')", "open('x')", "().__class__", "x.y", "lambda: 1", "[1,2][0:1]",
])
def test_unsafe_expressions_rejected(bad):
    res = parse_algorithm(f"START\nSET x = {bad}\nEND\n")
    assert not res["ok"]


def test_run_blocks_dangerous_code_and_times_out():
    assert check_python_safe("import os") is not None
    assert check_python_safe("open('f')") is not None
    res = run_python("while True:\n    pass\n")
    assert res["timedOut"]


def test_mod_div_and_equals_friendly_syntax():
    code = generate_python(ir_of('START\nINPUT n : int\nIF n mod 2 = 0 THEN\nPRINT n div 2\nEND IF\nEND\n'))
    assert "n % 2 == 0" in code and "n // 2" in code


def test_multiple_syntax_errors_with_line_and_column():
    from services.algorithm_text import check_algorithm
    text = "START\nINPUT n : int\nIF n > THEN\n    PRINT n *\nEND IF\nSET x = 5 +\nEND\n"
    res = check_algorithm(text)
    assert not res["ok"]
    lines = [e["line"] for e in res["errors"]]
    assert lines == [3, 4, 6]
    e = res["errors"][0]
    assert e["text"] == "IF n > THEN" and e["col"] >= 0 and e["length"] >= 1


def test_unclosed_block_points_to_opening_line():
    from services.algorithm_text import check_algorithm
    res = check_algorithm("START\nINPUT n : int\nWHILE n > 0 DO\n    SET n = n - 1\nEND\n")
    assert not res["ok"] and res["errors"][-1]["line"] == 3
    assert "END WHILE" in res["errors"][-1]["message"]


def test_meaning_problems_have_line_numbers():
    from services.algorithm_text import check_algorithm
    res = check_algorithm("START\nINPUT n : int\nPRINT total\nEND\n")
    assert res["ok"] and res["warnings"][0]["line"] == 3
    assert "total" in res["warnings"][0]["message"]


def test_pick_ollama_model_prefers_coder_and_skips_embeddings():
    from services.ai_provider import pick_ollama_model
    names = ["qwen3-embedding:0.6b", "glm-5.3:cloud", "qwen2.5-coder:7b", "gemma3:4b"]
    assert pick_ollama_model(names) == "qwen2.5-coder:7b"
    assert pick_ollama_model(["nomic-embed-text:latest"]) is None


def test_ai_settings_validation_and_secret_not_exposed(tmp_path, monkeypatch):
    from services import ai_settings
    monkeypatch.setattr(ai_settings, "PATH", str(tmp_path / "ai.json"))
    ok, _ = ai_settings.save({"provider": "openai", "openai_api_key": "sk-secret", "openai_model": "m1",
                              "ollama_model": "qwen2.5-coder:7b"})
    assert ok
    pub = ai_settings.public()
    assert pub["has_api_key"] is True and "openai_api_key" not in pub and "sk-secret" not in str(pub)
    assert ai_settings.load()["openai_api_key"] == "sk-secret"
    # empty key keeps the old one; bad values are rejected
    assert ai_settings.save({"openai_api_key": ""})[0]
    assert ai_settings.load()["openai_api_key"] == "sk-secret"
    assert not ai_settings.save({"provider": "evil"})[0]
    assert not ai_settings.save({"ollama_url": "file:///etc/passwd"})[0]
    assert not ai_settings.save({"ollama_model": "bad name; rm -rf"})[0]
    assert ai_settings.save({"ollama_model": ""})[0] and ai_settings.load()["ollama_model"] == ""


def test_ai_routes_reject_bad_input(tmp_path, monkeypatch):
    from app import create_app
    from services import ai_settings
    monkeypatch.setattr(ai_settings, "PATH", str(tmp_path / "ai.json"))
    c = create_app(str(tmp_path / "t.db")).test_client()
    assert c.post("/api/ai/pull", json={"name": "x; del *"}).status_code == 400
    assert c.post("/api/ai/delete", json={"name": ""}).status_code == 400
    assert c.post("/api/ai/settings", json={"provider": "nope"}).status_code == 400
    assert c.get("/api/ai/settings").get_json()["has_api_key"] is False


def test_disk_models_reads_downloaded_manifests(tmp_path, monkeypatch):
    import json as _json
    from services import ai_provider
    base = tmp_path / "manifests" / "registry.ollama.ai" / "library"
    (base / "qwen2.5-coder").mkdir(parents=True)
    (base / "qwen2.5-coder" / "7b").write_text(_json.dumps({"config": {"size": 10}, "layers": [{"size": 100}, {"size": 5}]}))
    (base / "nomic-embed-text").mkdir(parents=True)
    (base / "nomic-embed-text" / "latest").write_text(_json.dumps({"config": None, "layers": None}))
    monkeypatch.setenv("OLLAMA_MODELS", str(tmp_path))
    models = {m["name"]: m for m in ai_provider.disk_models()}
    assert models["qwen2.5-coder:7b"]["size"] == 115 and models["qwen2.5-coder:7b"]["usable"]
    assert not models["nomic-embed-text:latest"]["usable"]


def test_sum_and_product_generate_working_python():
    text = ('START\nINPUT n : int "n"\nSET s = Sum(i, 1, n, i^2)\nSET f = Prod(k, 1, n, k)\n'
            'PRINT s, f\nEND\n')
    code = generate_python(ir_of(text))
    assert "sum(" in code and "math.prod(" in code and "import math" in code
    out = run_python(code, "5\n")
    assert out["ok"], out
    assert "55 120" in out["stdout"]


def test_sum_counter_is_not_an_unknown_variable_and_arity_is_checked():
    assert validate_ir(ir_of('START\nINPUT n : int\nSET s = Sum(i, 1, n, i)\nEND\n'))["valid"]
    assert not parse_algorithm("START\nSET s = Sum(i, 1, 5)\nEND\n")["ok"]
    assert not parse_algorithm("START\nSET s = Sum(1, 1, 5, 2)\nEND\n")["ok"]


def test_empty_boxes_are_rejected_by_the_real_parser():
    res = parse_algorithm("START\nSET x = (\u25a1) / 2\nEND\n")
    assert not res["ok"] and "empty boxes" in res["errors"][0]["message"]


def test_formula_preview_latex_reading_and_hints():
    from services.formula_preview import preview
    names = ["start", "end", "low", "high"]
    r = preview("(start + end) / 2", "expression", names)
    assert r["latex"] == r"\frac{\mathrm{start} + \mathrm{end}}{2}"
    assert r["reading"] == "(start plus end) divided by 2"
    r = preview("start + end / 2", "expression", names)
    assert r["reading"] == "start plus (end divided by 2)" and r["ordered"] == "start + (end / 2)"
    assert any("write (start + end) / 2" in n["text"] for n in r["notes"])
    r = preview("(low + high) div 2", "expression", names)
    assert r["latex"].startswith(r"\left\lfloor") and r["python"] == "(low + high) // 2"
    r = preview("n mod 2 = 0", "condition", ["n"])
    assert r["latex"] == r"n \bmod 2 = 0" and r["python"] == "n % 2 == 0" and r["type"] == "true or false"
    r = preview("Sum(i, 1, n, i^2)", "expression", ["n"])
    assert r["latex"] == r"\sum_{i=1}^{n} i^{2}" and not r["notes"]
    r = preview("strat + 1", "expression", names)
    assert any("Did you mean 'start'" in n["text"] for n in r["notes"])
    r = preview("(\u25a1) / (\u25a1)", "expression", [])
    assert r["incomplete"] and r["latex"] == r"\frac{\square}{\square}" and r["python"] is None
    assert preview("n >", "condition", ["n"])["ok"] is False
    assert preview("", "expression", [])["empty"]


def test_formula_preview_route_and_unsafe_input():
    from app import create_app
    import tempfile
    c = create_app(os.path.join(tempfile.mkdtemp(), "t.db")).test_client()
    ok = c.post("/api/formula-preview", json={"text": "a[j] > a[j + 1]", "kind": "condition", "variables": ["a", "j"]}).get_json()
    assert ok["ok"] and ok["latex"] == "a_{j} > a_{j + 1}"
    bad = c.post("/api/formula-preview", json={"text": "__import__('os').system('dir')", "kind": "expression"}).get_json()
    assert bad["ok"] is False


def test_input_block_can_read_several_values_on_one_line():
    text = 'START\nINPUT a, b : int "Two numbers"\nPRINT a + b, a * b\nEND\n'
    code = generate_python(ir_of(text))
    assert "a, b = map(int, input('Two numbers: ').replace(',', ' ').replace('/', ' ').split())" in code
    out = run_python(code, "3 4\n")
    assert out["ok"] and "7 12" in out["stdout"]
    out = run_python(code, "3, 4\n")                       # a comma between the values also works
    assert out["ok"] and "7 12" in out["stdout"]
    # default prompt mentions all names; text type uses split(); round trip keeps the text
    code2 = generate_python(ir_of('START\nINPUT first, second : text\nPRINT first, second\nEND\n'))
    assert "first, second = input('Enter first, second (separated by spaces or commas): ').replace(',', ' ').split()" in code2
    assert "INPUT a, b : int" in print_algorithm(ir_of(text))
    assert any("2 whole numbers" in s["text"] for s in describe_steps(ir_of(text)))


def test_several_names_validation():
    assert not parse_algorithm("START\nINPUT a, b : list\nEND\n")["ok"]            # list needs one name
    assert not parse_algorithm("START\nINPUT a, a : int\nEND\n")["ok"]            # duplicate
    assert not parse_algorithm("START\nINPUT a, : int\nEND\n")["ok"]              # trailing comma
    ir = ir_of('START\nINPUT a, b : int\nPRINT a + b + c\nEND\n')
    assert any("'c'" in e["message"] for e in validate_ir(ir)["errors"])         # a and b are known, c is not
    ir = ir_of('START\nINPUT a, b : int\nPRINT a\nEND\n')
    ir["nodes"][1]["varType"] = "list_int"                                        # flowchart-side check
    assert not validate_ir(ir)["valid"]


def test_notes_become_comments_for_each_block_type():
    ir = ir_of('START\nINPUT n : int "n"\nSET d = n * 2\nIF d > 3 THEN\nPRINT d\nELSE\nPRINT 0\nEND IF\nEND\n')
    notes = {"start": "Program: double a number\nsecond line", "input": "n is read from the user",
             "process": "Formula: $d = n * 2$", "decision": "Check the size", "output": "show it", "end": "finished"}
    seen = set()
    for node in ir["nodes"]:
        if node["type"] in notes and node["type"] not in seen:
            node["note"] = notes[node["type"]]
            seen.add(node["type"])
    code = generate_python(ir)
    lines = code.splitlines()
    assert lines[2:4] == ["# Program: double a number", "# second line"]            # start note comes first
    assert lines.index("# n is read from the user") + 1 == lines.index("n = int(input('n: '))") - 0 or \
        lines[lines.index("# n is read from the user") + 1].startswith("n = int(")
    assert "# Formula: d = n * 2" in code                                            # $ signs are dropped
    assert lines[lines.index("# Check the size") + 1] == "if d > 3:"
    assert code.rstrip().endswith("# finished")
    compile(code, "<gen>", "exec")                                                    # still valid Python


def test_note_only_branch_still_valid_python():
    ir = ir_of('START\nINPUT n : int\nIF n > 0 THEN\nPRINT n\nEND IF\nEND\n')
    end = next(x for x in ir["nodes"] if x["type"] == "end")
    end["note"] = "nothing else to do"
    compile(generate_python(ir), "<gen>", "exec")


def test_comment_lines_in_algorithm_text_are_notes_and_round_trip():
    text = ('// whole program\nSTART\n// read the number\nINPUT n : int "n"\n// check it\nIF n > 0 THEN\n'
            '    // positive branch\n    PRINT n\nELSE\n    PRINT 0\nEND IF\n// last step\nEND\n')
    ir = ir_of(text)
    by_type = {}
    for n in ir["nodes"]:
        by_type.setdefault(n["type"], n)
    assert by_type["start"]["note"] == "whole program" and by_type["input"]["note"] == "read the number"
    assert by_type["decision"]["note"] == "check it" and by_type["output"]["note"] == "positive branch"
    assert by_type["end"]["note"] == "last step"
    assert print_algorithm(ir) == text.replace("// whole program\nSTART", "// whole program\nSTART")
    code = generate_python(ir)
    assert "# read the number" in code and "# positive branch" in code


def test_note_safety_and_validation():
    ir = ir_of('START\nPRINT 1\nEND\n')
    ir["nodes"][0]["note"] = "evil\nimport os\x00\rmore"
    code = generate_python(ir)
    assert "\nimport os" not in code                      # every note line stays a comment
    assert all(l.startswith("#") or not l.strip() or not l.startswith("import") for l in code.splitlines())
    ir["nodes"][0]["note"] = 5
    assert not validate_ir(ir)["valid"]
    ir["nodes"][0]["note"] = "x" * 1001
    assert not validate_ir(ir)["valid"]


def test_note_preview_splits_text_and_formulas():
    from services.formula_preview import preview
    r = preview("Roots: $x = (-b + sqrt(b^2 - 4*a*c)) / (2*a)$ done", "note", [])
    assert [list(s)[0] for s in r["segments"]] == ["text", "latex", "text"]
    assert r["segments"][1]["latex"].startswith("x = \\frac{")
    assert r["comment"] == ["# Roots: x = (-b + sqrt(b^2 - 4*a*c)) / (2*a) done"]
    bad = preview("Value $4ac$ and $5", "note", [])
    assert any("error" in s for s in bad["segments"]) and any("not closed" in n["text"] for n in bad["notes"])
    assert "4*a*c" in bad["segments"][1]["error"]
    assert preview("   ", "note", [])["empty"]


def _drive(code, typed, limit=15):
    """Run `code` through the console runner, typing each value when the program waits."""
    import time
    from services.interactive import RunManager
    run, problem = RunManager().start(code)
    assert run is not None, problem
    out, nxt, sent, waits = "", 0, 0, []
    deadline = time.time() + limit
    snap = {}
    while time.time() < deadline:
        snap = run.snapshot(nxt)
        out += snap["output"]
        nxt = snap["next"]
        if snap["waiting"] and sent < len(typed):
            waits.append(out)                      # what the console shows while it waits
            assert run.send_input(typed[sent])
            out += typed[sent] + "\n"
            sent += 1
        if snap["done"]:
            break
        time.sleep(0.03)
    return out, snap, waits


def test_console_run_pauses_at_each_input_and_continues():
    code = "a = int(input('First: '))\nb = int(input('Second: '))\nprint('Sum is', a + b)\n"
    out, snap, waits = _drive(code, ["3", "4"])
    assert waits == ["First: ", "First: 3\nSecond: "]            # prompt visible, no hidden marker
    assert out == "First: 3\nSecond: 4\nSum is 7\n"
    assert snap["done"] and snap["exitCode"] == 0 and snap["error"] == "" and "\x00" not in out


def test_console_run_reports_friendly_error_and_unicode():
    out, snap, _ = _drive("n = int(input('n: '))\nprint(n)\n", ["abc"])
    assert snap["done"] and snap["exitCode"] == 1 and "expected a whole number" in snap["error"]
    out, snap, _ = _drive("print('\u221a2 = 1.414')\nname = input('name: ')\nprint('hi', name)\n", ["\u03c0"])
    assert "\u221a2 = 1.414" in out and "hi \u03c0" in out


def test_console_run_can_be_stopped_and_blocks_dangerous_code():
    import time
    from services.interactive import RunManager
    mgr = RunManager()
    run, _ = mgr.start("x = input('wait: ')\nprint(x)\n")
    for _ in range(100):
        if run.snapshot()["waiting"]:
            break
        time.sleep(0.03)
    assert run.snapshot()["waiting"] and run.send_input("ok") and not run.send_input("again")   # only when waiting
    run2, _ = mgr.start("while True:\n    pass\n")
    time.sleep(0.3)
    run2.stop()
    for _ in range(100):
        if run2.snapshot()["done"]:
            break
        time.sleep(0.03)
    assert run2.snapshot()["done"] and run2.snapshot()["reason"] == "Stopped."
    assert mgr.start("import os")[0] is None


def test_console_routes():
    import time
    from app import create_app
    import tempfile
    c = create_app(os.path.join(tempfile.mkdtemp(), "t.db")).test_client()
    assert c.post("/api/run/start", json={"code": ""}).get_json()["ok"] is False
    assert c.post("/api/run/start", json={"code": "open('x')"}).get_json()["ok"] is False
    rid = c.post("/api/run/start", json={"code": "n = input('Name: ')\nprint('Hello', n)\n"}).get_json()["id"]
    for _ in range(100):
        snap = c.get(f"/api/run/{rid}/poll?since=0").get_json()
        if snap["waiting"]:
            break
        time.sleep(0.03)
    assert snap["output"] == "Name: " and snap["waiting"]
    assert c.post(f"/api/run/{rid}/input", json={"text": "Ada"}).get_json()["ok"]
    for _ in range(100):
        snap = c.get(f"/api/run/{rid}/poll?since={snap['next']}").get_json()
        if snap["done"]:
            break
        time.sleep(0.03)
    assert snap["output"] == "Hello Ada\n" and snap["exitCode"] == 0
    assert c.get("/api/run/nope/poll").status_code == 404
