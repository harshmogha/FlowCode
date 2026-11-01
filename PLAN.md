# FlowCode — Detailed Step-by-Step Build Plan

Companion to `README.md`. Each phase lists goals, tasks, files, deliverables, and a "done when" checklist. Build in order; do not start a phase until the previous one passes its checklist.

---

## 0. Overview and Timeline

| Phase | Name | Est. time |
|-------|------|-----------|
| 0 | Setup and environment | 0.5 day |
| 1 | Define the IR (JSON schema) and node specs | 1-2 days |
| 2 | Three-panel UI skeleton | 1-2 days |
| 3 | Drawflow editor and custom nodes | 3-4 days |
| 4 | Node property editing and diagram export | 2 days |
| 5 | Flask backend and validation | 3-4 days |
| 6 | Deterministic Python code generator | 3-4 days |
| 7 | AI provider layer (Ollama + online) | 3-4 days |
| 8 | Hybrid generation, multi-language | 3-4 days |
| 9 | Syntax check and sandboxed execution | 3 days |
| 10 | SQLite project save/load | 2 days |
| 11 | Polish, error UX, export | 2-3 days |
| 12 | Testing, documentation, demo | 3 days |

Total about 5-7 weeks part-time. First milestone (end of Phase 6): flowchart -> Python -> output, no AI needed.

---

## Phase 0 — Setup and Environment

**Goal:** working dev environment and repo.

Tasks:
1. Install Python 3.11+, Git, VS Code, and a modern browser.
2. Create project folder `flowcode/` with the structure from README section 5.
3. `python -m venv venv`, activate it.
4. `pip install flask requests pytest`; freeze to `requirements.txt` with pinned versions.
5. `git init`, add `.gitignore` (venv, `__pycache__`, `*.db`, `.env`).
6. Create `.env.example` (`AI_PROVIDER`, `OLLAMA_URL`, `OLLAMA_MODEL`, `OPENAI_API_KEY` etc.). Never commit real keys.
7. Optional: install Ollama and pull a coding model (e.g. `qwen2.5-coder`, `codellama`, `deepseek-coder`) for Phase 7.
8. Hello-world Flask route to confirm the server runs.

Done when: `python app.py` serves a page at `http://127.0.0.1:5000`.

---

## Phase 1 — Design the Intermediate Representation (IR)

**Goal:** a precise contract between frontend, validator, generator, and AI. Do this before any UI.

Tasks:
1. **Define node types and their fields:**

| Type | Fields | Outputs |
|------|--------|---------|
| start | label | 1 (next) |
| end | label | 0 |
| input | variable, prompt, varType (int/float/str) | 1 |
| output | value (expression or string), label | 1 |
| process | variable, expression (assignment) | 1 |
| decision | condition | 2 (`true`, `false`) |
| loop (while) | condition | 2 (`body`, `exit`) |
| (later) for-loop | variable, start, end, step | 2 |

2. **Define edges:** `{source, sourceHandle, target}`; handles named `next`, `true`, `false`, `body`, `exit`.
3. **Loop semantics:** condition evaluated before each iteration; the `body` branch must eventually return (edge) to the loop node; `exit` continues after the loop.
4. **Merge semantics:** after if/else, both branches may connect to the same next node (join).
5. **Variable rules:** identifier regex `^[A-Za-z_][A-Za-z0-9_]*$`, not a reserved keyword of any target language.
6. **Expression rules:** allowed subset: numbers, strings, variables, `+ - * / % //`, comparisons, `and or not`, parentheses. Decide a safe whitelist and parse with Python `ast` for validation.
7. Write `docs/ir_schema.json` (JSON Schema) and 5 sample diagrams as JSON fixtures in `tests/fixtures/`: even/odd, sum 1..n, factorial, max of two, fibonacci.

Deliverable: `docs/ir_schema.md`, schema file, fixtures.
Done when: all fixtures validate against the schema by hand/with `jsonschema`.

---

## Phase 2 — Three-Panel UI Skeleton

**Goal:** static layout, no logic yet.

Layout:
- **Left panel:** block palette (draggable items), project actions.
- **Center panel:** canvas (Drawflow container), toolbar (Validate, Generate, Clear, Zoom).
- **Right panel:** tabs — Properties | Code | Output | Errors; language dropdown; AI provider dropdown.

Tasks:
1. `templates/index.html` with semantic structure and CDN links (Drawflow CSS/JS).
2. `static/css/style.css`: CSS grid/flex, 3 columns, responsive min widths, dark/light theme variables.
3. Style palette items with distinct color/shape per node type (e.g. terminator = rounded, decision = diamond-like accent).
4. Accessibility: labels, keyboard focus, sufficient contrast.

Done when: layout renders cleanly at 1366x768 and larger.

---

## Phase 3 — Drawflow Editor and Custom Nodes

**Goal:** drag nodes from palette to canvas and connect them.

Tasks (`static/js/flowchart.js`):
1. Initialize `new Drawflow(container)`; `editor.start()`.
2. Implement HTML5 drag-and-drop from palette: `dragstart` sets node type, canvas `drop` computes canvas coordinates and calls `editor.addNode(...)`.
3. Node factory per type with correct input/output counts (decision: 1 in, 2 out; start: 0 in, 1 out; end: 1 in, 0 out; loop: 1+ in, 2 out).
4. Label output ports (`True/False`, `Body/Exit`) via CSS or node HTML.
5. Auto-name nodes (`input_1`, `decision_1`) and allow rename.
6. Connection rules in `connectionCreated`: prevent self-loop, only one `start` node, outputs allowed only one outgoing edge except where defined, reject invalid connections (remove them and show a message).
7. Delete node/connection via key or button; undo/redo (optional, store snapshots).
8. Zoom, pan, fit-to-screen, clear canvas.

Done when: the even/odd flowchart can be drawn entirely with the mouse.

---

## Phase 4 — Property Editing and Export

**Goal:** edit node data and produce IR JSON.

Tasks (`editor.js`, `api.js`):
1. On node select, show form in the Properties tab based on node type (fields from Phase 1).
2. Two-way binding: form edits update `node.data` in Drawflow and the node's visible text.
3. Client-side checks: variable name pattern, non-empty required fields.
4. `exportToIR()`: convert `editor.export()` to IR (`nodes`, `edges`, with handle names mapped from `output_1`, `output_2`). Strip coordinates (optionally keep in a separate `layout` field for reload).
5. `importFromIR()` to reload saved diagrams.
6. Save/restore to `localStorage` as interim persistence.
7. `api.js`: wrapper around `fetch()` with error handling for `/api/validate`, `/api/generate`, `/api/run`.

Done when: clicking Export prints correct IR JSON that matches fixtures for the even/odd diagram.

---

## Phase 5 — Flask Backend and Graph Validation

**Goal:** server-side validation (never trust the client).

Tasks:
1. `app.py`: app factory, routes `/`, `/api/validate`, `/api/generate`, error handlers returning JSON, size limit on request body.
2. `services/flow_validator.py` — implement checks:
   - exactly one start node; at least one end node
   - every non-end node has required outgoing edges (decision: both true and false; loop: body and exit)
   - no unreachable (disconnected) nodes — BFS/DFS from start
   - every path reaches an end (or a valid loop)
   - loops: body path returns to the loop node; detect unintended cycles (cycles not passing through a loop node)
   - variable names valid and not reserved
   - variables used before assignment (data-flow check along paths)
   - expressions parse with `ast` and only use whitelisted nodes
   - no duplicate node ids; edges reference existing nodes
3. Return structured results: `{valid: bool, errors: [{nodeId, code, message}], warnings: [...]}`.
4. Frontend: highlight offending nodes (red border) and list messages in Errors tab; clicking an error selects the node.
5. Unit tests in `tests/test_validator.py`: one test per rule, valid and invalid fixtures.

Done when: all invalid fixtures return correct errors, valid fixtures pass.

---

## Phase 6 — Deterministic Python Code Generator (First Milestone)

**Goal:** correct Python from the IR without AI. This is the ground truth and fallback.

Tasks (`services/code_generator.py`):
1. Build adjacency map; traverse from start.
2. Structured conversion algorithm:
   - Linear nodes: emit statements.
   - Decision: emit `if cond:` / `else:`; find the **join node** (immediate post-dominator) so code after the if/else is emitted once.
   - Loop: emit `while cond:` with body; continue from `exit`.
   - Handle nested decisions/loops via recursion with a "stop at node" parameter.
3. Input handling: `int(input(prompt))` etc. based on `varType`.
4. Output: `print(value)`.
5. Indentation manager and pretty output.
6. Reject non-structured graphs (e.g. goto-like jumps) with a clear message, or document the limitation.
7. Tests in `tests/test_generator.py`: generate code for every fixture, `compile()` it, run with sample input, compare output.
8. Wire `/api/generate` with `mode=template`; show code in Code tab with copy button.

Done when: even/odd, sum, factorial, nested if, and while-loop fixtures produce correct runnable Python. **Milestone 1 reached.**

---

## Phase 7 — AI Provider Layer

**Goal:** swap models without changing the rest of the app.

Tasks (`services/ai_provider.py`):
1. Abstract base class `AIProvider.generate(ir, language, options) -> str`.
2. `OllamaProvider`: POST to `http://localhost:11434/api/generate` or `/api/chat`, `stream=false`, timeout, model name from settings.
3. `OnlineProvider` (one choice first, e.g. OpenAI/Gemini/other compatible API): API key from env/settings, handle rate limit and timeouts.
4. Prompt template (store in `services/prompts.py`):
   - system: "You are a code generator. Follow the algorithm exactly. Output only code in a single fenced block. No extra logic."
   - user: language, IR JSON, rules (variable names preserved, input/output semantic, language idioms).
5. Response parsing: extract code block, strip prose.
6. Settings endpoint `/api/settings` and UI dropdown (provider, model, API key field stored server-side only, never in frontend code or git).
7. Error handling: model unreachable -> clear message + automatic fallback to template generator.
8. Privacy note in UI when an online provider is selected.

Done when: the same diagram generates Python via Ollama and via the online API, and via template as fallback.

---

## Phase 8 — Hybrid Generation and Multi-Language

**Goal:** reliable output for Java, C++, etc.

Tasks:
1. Strategy: template generates a **reference Python** solution; AI converts/generates target language from IR and reference, preserving behavior.
2. Add template generators for **Java** and **C++** for basic constructs (Scanner / `cin`, `System.out.println` / `cout`, main wrappers, variable declarations with types). Use AI for complex expressions and cleanup.
3. Add optional explanation mode: AI explains the generated code step by step.
4. Add AI "review" pass: compare generated code with IR and report mismatches (optional).
5. Language dropdown: Python, Java, C++ (extend list via config).
6. Handle language-specific rules: type declarations, semicolons, reserved words, integer division behavior.

Done when: even/odd and loop fixtures generate compilable Java and C++ (verify with `javac` / `g++` if installed).

---

## Phase 9 — Code Validation and Safe Execution

**Goal:** verify generated code and run test cases safely.

Tasks (`services/executor.py`):
1. **Syntax check:** Python `compile()`; Java `javac`; C++ `g++ -fsyntax-only` (if compilers available; otherwise skip with notice).
2. **Execution sandbox (choose one, simplest first):**
   - Subprocess with timeout, memory limits, temp directory, no shell, stripped environment.
   - Better: Docker container with `--network none`, CPU/memory limits, read-only filesystem.
3. Run generated code with user-supplied stdin; capture stdout/stderr; enforce timeout (e.g. 5 s) and output size limit.
4. Test-case panel in UI: list of (input, expected output), run all, show pass/fail.
5. Never run code in the Flask process; never use `eval/exec` on user code.
6. If the AI result fails tests: show diff, offer "retry generation" or "use template result".
7. Rate-limit `/api/run`.

Done when: code runs in isolation, infinite loops are killed by timeout, and results show in the Output tab.

---

## Phase 10 — Persistence (SQLite)

Tasks:
1. `database/db.py`: connection helper; create table `projects(id, name, language, diagram_json, generated_code, created_at, updated_at)`; optional `test_cases` table.
2. Endpoints: `GET/POST /api/projects`, `GET/PUT/DELETE /api/projects/<id>`. Use parameterized queries only.
3. UI: Save, Save As, Open dialog (list projects), Delete, auto-save indicator.
4. Export: download source file (`.py/.java/.cpp`), download diagram JSON, import diagram JSON, export canvas as PNG (optional).

Done when: close the browser, reopen, load project, and diagram and code are restored exactly.

---

## Phase 11 — Polish and UX

Tasks:
1. Replace code textarea with Monaco Editor (optional) with syntax highlighting per language.
2. Loading spinners and disabled buttons during generation; cancel request.
3. Friendly error messages with fix hints; node-level error badges.
4. Keyboard shortcuts (Delete, Ctrl+S, Ctrl+Z).
5. Example gallery: one-click load of sample algorithms.
6. Execution tracing (stretch): highlight nodes step by step using a template-based interpreter.
7. Responsive layout check, theme toggle, tooltips on palette items.

---

## Phase 12 — Testing, Documentation, Demo

Tasks:
1. Unit tests: validator, generator, IR conversion, provider parsing (mock HTTP), executor limits.
2. Integration tests: Flask test client hitting each endpoint with fixtures.
3. Manual test checklist: draw, invalid graph, each language, provider switch, save/load.
4. Security review: input size limits, no secret leakage, sandbox flags, CORS off by default, CSRF considerations if you add forms.
5. Documentation: update README with screenshots, setup guide, architecture diagram, limitations.
6. Demo script (5 minutes): even/odd -> loop sum -> invalid diagram error -> switch language -> run tests -> save/load.
7. Final report/presentation: problem, architecture, IR, hybrid approach, results, future work.

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|-----------|
| AI output wrong or inconsistent | High | Template ground truth, tests, validation, fallback |
| Unstructured flowcharts (arbitrary jumps) | Medium | Enforce structured blocks in v1, validate and explain |
| Unsafe code execution | High | Sandbox, timeouts, no network, never in main process |
| Local model too slow/weak | Medium | Smaller prompts, template-first, allow online provider |
| Scope creep | Medium | Freeze v1 at Python + Phase 6 milestone, then add languages |
| API keys leaked | High | `.env`, gitignore, server-side only |

## Definition of Done (v1)

- Draw a flowchart with all 7 block types via drag-and-drop.
- Invalid diagrams produce clear, node-linked errors.
- Python code generated deterministically and via AI; matches flowchart logic.
- At least Java or C++ generated in addition to Python.
- Code runs in a sandbox against test cases with results shown.
- Projects save/load via SQLite; code downloadable.
- Automated tests pass; README and demo prepared.

## Suggested Weekly Schedule

- **Week 1:** Phases 0-3
- **Week 2:** Phases 4-5
- **Week 3:** Phase 6 (milestone demo) 
- **Week 4:** Phase 7
- **Week 5:** Phases 8-9
- **Week 6:** Phases 10-11
- **Week 7:** Phase 12, buffer, final demo


---

# ADDENDUM — Algorithm Mode and Mathematical Formula Support

New requirement: besides drawing a flowchart, the user can **write the algorithm as text**, and can use **mathematical formulas in proper mathematical notation** in either mode. See `README.md` section 13 for syntax, notation table, and IR format.

This addendum inserts new phases into the main plan. Phase numbers with a letter (for example `1A`) are inserted after the numbered phase and before the next one. Existing phases are unchanged unless noted under "Changes to existing phases".

## Updated Timeline

| Phase | Name | Est. time |
|-------|------|-----------|
| 1A | Algorithm grammar and math notation spec | 2 days |
| 4A | Formula editor (MathLive + KaTeX) | 2-3 days |
| 5A | Expression parser and AST validation | 3-4 days |
| 5B | Algorithm text parser (text -> IR) | 3-4 days |
| 5C | Algorithm printer and flowchart <-> algorithm sync | 3 days |
| 6A | Expression translator (AST -> Python/Java/C++) | 3 days |
| 12A | Math-focused tests and cross-check | 2 days |

Added effort: about 3 weeks part-time. New total: about 8-10 weeks part-time. The Milestone 1 demo (Phase 6) now includes formulas and algorithm text for Python.

---

## Phase 1A — Algorithm Grammar and Math Notation Spec

**Goal:** freeze exactly what users may write, before building parsers.

Tasks:
1. Write `docs/algorithm_grammar.md` with a formal grammar (EBNF) for: `START`, `END`, `INPUT`, `SET` / `<-` / `←`, `PRINT`, `IF/THEN/ELSE/END IF`, `WHILE/DO/END WHILE`, `FOR/FROM/TO/STEP/DO/END FOR`, comments, and blank lines. Define keyword case rules and indentation (indentation optional; block ends are explicit).
2. Write `docs/formula_support.md`: the full notation table from README 13.3 (LaTeX input, text input, meaning, type of result, Python/Java/C++ output).
3. Fix precedence and associativity rules, typing rules (`int`, `float`, `string`, `bool`), and the rule that `\frac` is real division while integer division uses floor.
4. Decide implicit multiplication policy (single-letter variables only; multi-letter names via `\text{}` or text mode) and write ambiguity warnings.
5. Decide handling of `\pm` (expand to two assignments), `\sum`/`\prod` (loop accumulators), and subscripts (`x_{1}` -> `x1`, `a_{i}` -> `a[i]` when `a` is declared as array).
6. Extend the IR schema (`docs/ir_schema.json`): expression objects with `latex`, `text`, `ast`; top-level `mode` and `source_text`; AST node format: `{"num": v}`, `{"var": name}`, `{"str": s}`, `{"op": name, "args": [...]}`, `{"sum": {...}}`.
7. Add fixtures: for each example in README 13.8, store `algorithm.txt`, `ir.json`, sample inputs, and expected outputs in `tests/fixtures/`.

Done when: another person can read the two docs and know exactly which inputs are valid, and every fixture validates against the schema.

---

## Phase 4A — Formula Editor (MathLive + KaTeX)

**Goal:** users write formulas in real math notation in node properties and in algorithm mode.

Tasks (`static/js/formula_editor.js`):
1. Add MathLive and KaTeX via CDN (pin versions).
2. Replace plain expression inputs in the Properties panel (condition, expression, output value) with a `<math-field>` plus a toggle to "text/LaTeX" mode.
3. Build a symbol toolbar: fraction, power, subscript, square root, n-th root, absolute value, floor, ceiling, sum, product, pi, e, trig, log, comparison symbols, logic symbols, factorial, binomial.
4. On change, store `latex` (and `text` form) in node data; send to `/api/parse-expression` for AST (Phase 5A); show the parse result or error under the field.
5. Render the formula on the flowchart block itself with KaTeX (the block shows `x1 = (−b+√D)/2a` as a real fraction and root).
6. Mark custom vars: autocomplete variable names already defined in the diagram.
7. Accessibility: keyboard-only entry; provide the LaTeX text mode as a fallback.
8. Make sure Drawflow node HTML re-renders when the formula changes.

Done when: the quadratic formula can be entered by clicking toolbar buttons, appears rendered on the block, and its LaTeX is stored in node data.

---

## Phase 5A — Expression Parser and AST Validation

**Goal:** convert any accepted formula (LaTeX or text) into a safe AST on the server.

Tasks (`services/expression_parser.py`):
1. Choose approach:
   - Text expressions: Python `ast` module with a strict whitelist of node types (no calls other than approved functions, no attribute access, no imports).
   - LaTeX expressions: either accept MathJSON from the client (MathLive Compute Engine) and normalize it, or write a small LaTeX parser (tokenizer + recursive descent) for the supported notation. Prefer the option that gives a deterministic, testable result; do not use `eval`.
2. Normalize both inputs to the common AST format from Phase 1A.
3. Handle: operators, `\frac`, powers, roots, absolute value, floor/ceil, factorial, functions, constants, subscripts, comparisons, logic, `\sum`, `\prod`, `\binom`.
4. Implicit multiplication resolution using declared single-letter variables; emit ambiguity warnings.
5. Static analysis on the AST:
   - undefined variables (using data-flow from Phase 5)
   - type inference (int/float/string/bool) and type warnings
   - domain warnings (division by zero risk, negative sqrt, non-positive log, invalid factorial)
6. Return `{ast, text, type, warnings, errors}` with positions where possible.
7. Endpoint `/api/parse-expression`.
8. Unit tests: every row of the notation table, precedence cases (`-2^2`, `a/b*c`), malicious inputs (`__import__('os')`, `().__class__`) must be rejected.

Done when: every supported formula in `tests/fixtures` produces the expected AST, and unsafe or unsupported inputs return clear errors.

---

## Phase 5B — Algorithm Text Parser (Text -> IR)

**Goal:** the user types an algorithm; the app builds the IR (and therefore the flowchart).

Tasks (`services/algorithm_parser.py`, `static/js/algorithm_editor.js`):
1. Tokenizer: keywords, identifiers, numbers, strings, `$...$` LaTeX segments, operators, comments, line/column tracking.
2. Recursive-descent parser following the grammar in Phase 1A, producing structured nodes: sequence, if/else, while, for.
3. Convert the structured tree to IR nodes and edges: create explicit `start`, `end`, `decision` (true/false edges), `loop` (body/exit with back-edge); lower `FOR` into init + `while` + increment (or keep a `for` node type if added to the IR).
4. Parse every expression with Phase 5A; attach `latex`, `text`, `ast`.
5. Error reporting with line/column and a suggested fix ("Expected END IF to close IF on line 3").
6. Frontend algorithm editor: line numbers, keyword highlighting, inline error markers, formulas inside `$...$` rendered in a preview pane with KaTeX; optional Monaco Editor with a custom language definition.
7. Endpoint `/api/parse-algorithm` returning IR + errors.
8. Auto-layout: place generated nodes top-to-bottom, branches side by side, using a simple layered layout algorithm; allow manual dragging afterwards.
9. Optional "Describe mode": send plain English to the AI to draft pseudocode in this grammar; show it in the editor for the user to review and edit; never auto-run unreviewed output.
10. Tests: each fixture `algorithm.txt` yields exactly the expected `ir.json`; malformed inputs yield the expected error messages.

Done when: the even/odd and quadratic algorithms typed as text produce a correct, validated IR and a drawn flowchart.

---

## Phase 5C — Algorithm Printer and Two-Way Sync

**Goal:** flowchart and algorithm text always agree.

Tasks (`services/algorithm_printer.py`, `static/js/mode_sync.js`):
1. IR -> pseudocode printer using the same structured traversal as the code generator (join detection for if/else, loop bodies). Formulas are written as `$latex$`.
2. Split view: left flowchart, right algorithm text. Edits on one side update the other with debounce (about 500 ms).
3. Conflict policy: the last edited side wins; if the flowchart has structure that cannot be printed as structured text (arbitrary jumps), show a warning and keep the text read-only.
4. Layout preservation: when text is edited and the flowchart regenerates, preserve positions of nodes whose ids are unchanged.
5. Mode switcher UI (Flowchart | Algorithm | Split) and unsaved-change handling.
6. Round-trip tests: text -> IR -> text equals the normalized original; IR -> text -> IR gives the same graph.

Done when: editing either view updates the other correctly for all fixtures.

---

## Phase 6A — Expression Translator (AST -> Code)

**Goal:** exact formula translation per language, without AI.

Tasks (`services/expression_translator.py`):
1. Visitor over the AST with a language back-end interface: `translate(ast, language) -> string` plus required imports and helper functions.
2. Python: use `math` functions, `**`, `//`, `%`; add `import math` only if needed.
3. Java: `Math.*`, `Math.pow`, explicit `(double)` casts for real division, helper static methods for factorial/binomial/gcd.
4. C++: `<cmath>`, `std::pow`, `std::min/max`, `<numeric>` for gcd, helper functions for factorial/binomial.
5. `\sum` and `\prod`: emit a helper loop or inline accumulator with a generated temporary variable; ensure unique temp names.
6. Parenthesize according to precedence so output is correct and readable (no redundant parentheses).
7. Variable naming: map `x_{1}` -> `x1`, avoid target-language reserved words (`class`, `int`, `new`, ...), keep names consistent across the program.
8. Integrate into Phase 6 code generator: statements use the translator for every expression.
9. Tests: for each notation row, evaluate expression in Python and compare with compiled Java/C++ output on sample values (tolerance for floats).

Done when: all example algorithms produce correct Python, and Java/C++ expressions compile and match Python results.

---

## Phase 12A — Math-Focused Testing and Cross-Check

Tasks:
1. Reference evaluator: compute each formula directly from the AST in Python (and SymPy where useful) to obtain expected values.
2. For each example algorithm in README 13.8, run generated code in the sandbox with several inputs, including edge cases (zero, negative, large values, `D = 0` for the quadratic).
3. Compare outputs to the reference with a float tolerance; report mismatches in the UI test panel.
4. Property tests: random numeric inputs for pure formulas; the template result and the AI result must agree.
5. Security tests for the expression parser (injection attempts) and the algorithm parser (very long input, deeply nested blocks, resource limits).
6. Usability test: ask 3-5 classmates to write two algorithms using the formula editor and record problems.

Done when: all formula examples pass in all supported languages and unsafe input is rejected.

---

## Changes to Existing Phases

| Phase | Change |
|-------|--------|
| 1 | IR expression fields become objects (`latex`, `text`, `ast`); add `mode` and `source_text` |
| 2 | Add mode switcher and an algorithm panel area to the layout |
| 3 | Node blocks display rendered formulas (KaTeX) |
| 4 | Export/import IR includes formula objects; `localStorage` saves `mode` and `source_text` |
| 5 | Validator runs on AST: undefined variables, types, domain warnings |
| 6 | Statements use the expression translator (Phase 6A) rather than raw strings |
| 7 | Prompts include the AST and the target-language expression produced by the translator, so the AI must reuse them verbatim |
| 8 | Java/C++ generators use the translator back-ends; AI only handles structure and idioms |
| 9 | Test panel supports numeric tolerance for floating-point results |
| 10 | SQLite `projects` gets columns `mode` and `source_text` |
| 11 | Example gallery contains the math-heavy algorithms from README 13.8 |

## Additional Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| LaTeX/MathJSON parsing ambiguity (implicit multiplication, `\frac` nesting) | High | Strict spec in Phase 1A, ambiguity warnings, tests for every notation row |
| Unsafe formula evaluation (`eval`) | High | Whitelist parser only; never `eval`; injection tests |
| Float differences across languages | Medium | Tolerance in tests, document behaviour |
| Text <-> flowchart round-trip loses structure | Medium | Single IR as source of truth, round-trip tests, read-only fallback |
| Formula library API changes | Low | Pin CDN versions; store LaTeX/AST so the editor can be replaced |
| Scope growth (too many symbols) | Medium | Support only the table in README 13.3 in v1 |

## Updated Definition of Done (additions)

- The user can write an algorithm in text, using the defined grammar, and see the matching flowchart.
- Editing the flowchart updates the algorithm text and vice versa.
- Formulas can be entered in math notation (fraction, power, root, sum, product, etc.), displayed rendered, and translated correctly to Python and at least one of Java/C++.
- Invalid syntax, unknown symbols, and unsafe formulas produce clear, located error messages.
- All example algorithms in README 13.8 pass their tests.

## Updated Weekly Schedule

- **Week 1:** Phases 0, 1, 1A, 2
- **Week 2:** Phases 3, 4, 4A
- **Week 3:** Phases 5, 5A
- **Week 4:** Phases 5B, 5C
- **Week 5:** Phases 6, 6A (Milestone 1 demo: flowchart or text -> formula-aware Python)
- **Week 6:** Phase 7
- **Week 7:** Phases 8, 9
- **Week 8:** Phases 10, 11
- **Week 9:** Phases 12, 12A
- **Week 10:** Buffer, documentation, final demo


---

# ADDENDUM 2 — Word-Style Formula Template Gallery

New requirement: the formula editor provides ready-made structure templates grouped like Word's equation ribbon (Fraction, Script, Radical, Integral, Large Operator, Bracket, Function, Accent, Operator, Matrix), each with placeholder boxes. The catalogue, LaTeX forms, and run status of every template are in `README.md` section 14.

## Updated Timeline (additions)

| Phase | Name | Est. time |
|-------|------|-----------|
| 4B | Formula template catalogue (data) | 2 days |
| 4C | Ribbon and gallery UI | 3-4 days |
| 5D | Parser support for template semantics (tier 1) | 3 days |
| 6B | Tier 1 translators for scripts, big operators, accents | 2 days |
| 13 | Tier 2 features (post-v1): integrals, derivatives, limits, matrices, sets | 2-3 weeks |

Added effort for v1: about 1.5-2 weeks part-time. Tier 2 (Phase 13) is optional after the v1 demo.

---

## Phase 4B — Formula Template Catalogue (Data)

**Goal:** one source of truth for every template.

Tasks:
1. Create `static/js/formula_templates.json` with one entry per template in README 14.2 (id, category, group, label, latex, ast_op, status, tooltip, example).
2. Group entries exactly as the ribbon: categories, then groups, then "Common ..." groups.
3. Assign a status (R/A/D) to each, following README 14.3.
4. Write `docs/formula_catalogue.md` from the JSON (small script) so documentation never drifts.
5. Add a check script that fails if a template has no status, duplicate id, or LaTeX that does not render in KaTeX.

Done when: the JSON validates, every template renders in KaTeX, and the catalogue document is generated.

---

## Phase 4C — Ribbon and Gallery UI

**Goal:** a Word-like insertion experience.

Tasks (`static/js/formula_gallery.js`, `style.css`):
1. Ribbon bar above the formula field with buttons: Fraction, Script, Radical, Integral, Large Operator, Bracket, Function, Accent, Operator, Matrix, each with a dropdown arrow.
2. Dropdown galleries: dark tile grid with group headings ("Fraction", "Common Fraction", ...), tiles show a rendered preview of the template with dotted placeholder boxes.
3. Click inserts the template into the active math field with placeholders (use the editor's placeholder feature; verify the exact API in the library docs); selected text goes into the first placeholder.
4. Keyboard: `Tab`/`Shift+Tab` between placeholders, `Esc` exits; inline shortcuts like `\frac`, `\sqrt`, `/`.
5. Status badges on tiles (Runs / Approximate / Display only) with tooltips.
6. Matrix dialog: choose rows and columns (not limited to 3x3), bracket style, and identity or empty fill; rows/columns editable after insertion.
7. "Recently used" row and optional search box ("sqrt", "integral").
8. Works in Properties panel fields and in the algorithm editor formula popup (`$...$` insertion).
9. Accessibility: tiles are buttons with labels, gallery navigable by keyboard.

Done when: the quadratic formula, Pythagorean expression, a summation, and a 2x2 matrix can each be inserted from the ribbon and filled in with the mouse only.

---

## Phase 5D — Parser Support for Template Semantics

**Goal:** the expression parser (Phase 5A) understands every tier 1 template and reports tiers 2 and 3 correctly.

Tasks:
1. Map each template `ast_op` to AST nodes: `div`, `pow`, `index`, `sqrt`, `root`, `abs`, `floor`, `ceil`, `sum`, `prod`, `any`, `all`, `log`, `ln`, trig set, `min_range`, `max_range`, `accent_name`, compound assignment operators.
2. Subscript rules: integer or single-name subscripts only; nested subscripts rejected with a clear message.
3. Accent rule: accent on a single variable becomes a decorated identifier (`x_bar`); accent on a larger expression is display only.
4. `\pm` handling inside `\frac` for the quadratic formula: expand to two assignments automatically and show the user the two generated statements.
5. Tier 2 constructs (integral, derivative, limit, matrices, sets, cases): parse to AST nodes marked `tier: 2` and return a warning "approximate / not yet supported in the selected language" so they can be stored and rendered.
6. Tier 3 constructs: parse to a `display` node; reject in executable fields; accept in Note nodes.
7. Tests in `tests/test_formula_templates.py`: for every catalogue entry, insert its example, parse it, and assert the expected AST kind and status.

Done when: all tier 1 examples parse to the expected AST, and tier 2/3 examples give the correct warnings.

---

## Phase 6B — Translators for Tier 1 Template Operations

**Goal:** generated code for scripts, big operators, accents, and discrete min/max.

Tasks (`services/expression_translator.py`):
1. `sum`/`prod`: loop accumulator (inclusive bounds; bounds must be integers; empty range returns 0 or 1).
2. `any`/`all` for big OR/AND over a range.
3. `min_range`/`max_range` over a discrete index range (loop with running best).
4. `index`: `a_i` -> `a[i]` (Python, Java, C++); check array declared; zero- vs one-based indexing option (default: one-based in the algorithm and converted by the generator, documented clearly).
5. Accent names: `x_bar`, `x_hat`, `v_vec`, `x_dot` as plain identifiers, checked for collisions with other variables.
6. Compound assignment operators `+=`, `-=` emitted natively in all three languages.
7. `log_b x`: Python `math.log(x, b)`; Java/C++ `log(x)/log(b)`.
8. Trigonometric functions: radians by default; optional degree mode inserts conversion.
9. Tests: every Tier 1 template compiled and compared with a Python reference value in all supported languages.

Done when: Tier 1 examples generate correct Python, Java, and C++ and match the reference results.

---

## Phase 13 (Post-v1) — Tier 2 Features

Only start after the v1 demo is working. Do in this order of value:

1. **Definite integrals and derivatives (numeric).** Helper `integrate(f, a, b, n=1000)` using Simpson's rule; numeric derivative by central difference with step `h=1e-5`; generate the function `f` from the AST; show an "approximate" badge and a tolerance in tests.
2. **Limits (numeric).** Evaluate at points approaching the target from both sides; report convergence or "could not converge"; infinity handled by large values; always labelled approximate.
3. **Matrices.** Add `matrix` AST node, 2D arrays in each language (`list`, `double[][]`, `vector<vector<double>>`); helpers for add, scalar multiply, product, transpose, determinant, inverse, identity; dimension checks at validation time.
4. **Sets and union/intersection** over an index range; set literals `\{...\}`.
5. **Cases (piecewise).** Translate to if/else or a conditional expression.
6. **Complex numbers** (`i` as the imaginary unit; `cmath` in Python, `std::complex` in C++, custom class in Java).
7. **Double integrals** with rectangular limits (nested Simpson).
8. Keep contour/surface/volume integrals, co-products, pre-scripts, and annotation arrows as display-only unless a clear need appears.

Done when: each included item has parser, translator, validator checks, UI badge changed from D/A to R/A as appropriate, and tests.

---

## Changes to Earlier Phases

| Phase | Change |
|-------|--------|
| 1A | Include the catalogue in the formula spec; add status tiers and the display-only rule |
| 4A | Use the gallery (4B/4C) as the main way to insert structures; toolbar from 4A becomes the "Recently used" and quick-symbol row |
| 5A | Parser consumes `ast_op` from the catalogue; adds tier and status to results |
| 6A | Translator implements tier 1 operations from 6B |
| 8 | Java and C++ helper functions for factorial, binomial, gcd, sum/product loops are reused for tier 1 operators |
| 11 | Add gallery search, keyboard shortcuts help, and formula examples in the gallery |
| 12A | Add a test that inserts every template through the UI automation (or a JS unit test of the template engine) |

## Additional Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Library lacks some symbols or structures (e.g., contour/surface integrals, certain arrows) | Medium | Mark as display-only; fallback glyphs; keep the catalogue data-driven |
| Users expect every template to generate code | High | Visible status badges, tooltips, clear error messages, tier table in docs |
| Numeric integration/limits give wrong results for hard functions | Medium | Approximate badge, warnings, tolerances, default step settings user-adjustable |
| Ambiguity of `dy/dx`, subscripts, and implicit multiplication | High | Derivative only from the template; strict subscript rules; ambiguity warnings |
| Matrix support grows scope | Medium | Keep matrices store-and-render only in v1; operations in Phase 13 |

## Updated Definition of Done (additions)

- The formula editor has a Word-style ribbon with Fraction, Script, Radical, Integral, Large Operator, Bracket, Function, Accent, Operator, and Matrix galleries.
- Every template shows its status; all Tier 1 templates generate correct code in Python and at least one of Java/C++.
- Display-only and approximate templates are rendered, saved, and clearly flagged.
- The catalogue JSON, generated catalogue document, and tests agree.

## Updated Weekly Schedule

- **Week 1:** Phases 0, 1, 1A, 2
- **Week 2:** Phases 3, 4, 4A
- **Week 3:** Phases 4B, 4C
- **Week 4:** Phases 5, 5A, 5D
- **Week 5:** Phases 5B, 5C
- **Week 6:** Phases 6, 6A, 6B (Milestone 1 demo)
- **Week 7:** Phase 7
- **Week 8:** Phases 8, 9
- **Week 9:** Phases 10, 11
- **Week 10:** Phases 12, 12A
- **Week 11:** Buffer, documentation, final demo
- **After v1:** Phase 13 (tier 2)


---

# ADDENDUM 3 — Readable Formula Entry (Preview, Explanation, Variable Awareness)

New requirement: a user typing something like `start + end / 2` must be able to enter it easily, see it as real maths, and understand what it means. Details in `README.md` section 15.

## Updated Timeline (additions)

| Phase | Name | Est. time |
|-------|------|-----------|
| 4D | Formula preview panel and variable awareness | 3-4 days |
| 5E | Explanation generator and precedence helper | 2-3 days |
| 5F | Rendered algorithm (textbook) view | 2 days |

Added effort: about 1.5 weeks part-time.

---

## Phase 4D — Formula Preview Panel and Variable Awareness

**Goal:** the user always sees what they wrote as real maths and cannot confuse multi-letter names.

Tasks:
1. Preview panel under every formula field with five rows: Typed, Rendered (KaTeX), Reads as, Target-language code, Type check.
2. Text-to-math conversion: when the user types plain text such as `(start + end) / 2`, parse it on a short debounce and show the rendered fraction; keep the original text editable.
3. Auto-fraction: typing `/` after a term or a bracketed group converts to a stacked fraction and moves the cursor to the denominator (verify the library's option for this behaviour).
4. Variables list: collect all variables from the current IR (`INPUT`, `SET`, loop variables, node names) and show them as chips beside the field; clicking inserts the variable.
5. Tokenizer rule: match identifiers longest-first against declared variables; undeclared multi-letter names give the warning "Did you mean ...?" using edit distance, with a one-click fix.
6. Reserved-word detection: if a variable is named `start`, `end`, `if`, `for`, `while`, `print`, or a target-language keyword, show a rename suggestion (`low/high`, `lo/hi`, `first/last`).
7. Render variables upright and coloured to distinguish them from single-letter symbols.
8. Add templates "Round down (floor of a quotient)" and "Remainder" to the Bracket/Operator galleries (catalogue update in `formula_templates.json`).
9. Subscript equivalence: `a[j+1]` and `a_{j+1}` normalise to the same AST and render the same.

Done when: `(start + end) / 2` and `floor((start + end) / 2)` can be entered in all four ways and show correct rendering, while `start + end / 2` shows the "Did you mean" hint.

---

## Phase 5E — Explanation Generator and Precedence Helper

**Goal:** make each formula self-explanatory.

Tasks (`services/expression_explainer.py`):
1. AST-to-English generator with a phrase for every AST op (add, sub, mul, div, pow, sqrt, abs, floor, ceil, mod, sum, prod, comparison, logic, index, function calls). Use the variable names as written; use "squared"/"cubed" for powers 2 and 3.
2. Add disambiguating wording ("start plus end, divided by 2" vs "start plus (end divided by 2)"), using brackets in the sentence whenever precedence matters.
3. Parenthesised view: print the AST with explicit brackets for every binary operation.
4. Numeric preview: ask the user for sample values (or use stored test inputs) and show the evaluated step-by-step result using the reference evaluator.
5. "Did you mean" heuristic: when an expression of the form `a + b / c` or `a - b * c` appears and the variable names suggest a grouping (e.g. `start`, `end`, `low`, `high` in the same sum), show a non-blocking suggestion; never change the formula automatically.
6. Type check: infer integer vs decimal result; warn when a decimal is used as an array index or loop counter; recommend the floor template.
7. Optional "Explain with AI" button: send the AST and ask for a longer explanation; label the output as AI-generated.
8. Tests: explanation strings for every AST op; precedence cases; type-check warnings.

Done when: the explanation for each example in README 15.5 matches the expected text.

---

## Phase 5F — Rendered Algorithm (Textbook) View

**Goal:** show the whole algorithm with formulas typeset.

Tasks:
1. Add a read-only pane that renders each algorithm line: keywords in bold, variables upright, formulas in KaTeX.
2. Keep line numbers in sync with the text editor; clicking a rendered line moves the cursor to the matching text line, and vice versa.
3. Show formula warnings (type, domain, ambiguity) as icons next to the rendered line.
4. Export the textbook view as PDF or image (stretch).

Done when: the binary-search and bubble-sort fixtures display correctly typeset.

---

## Changes to Earlier Phases

| Phase | Change |
|-------|--------|
| 1A | Grammar adds array access `a[i]` and array input `INPUT a[1..n]`; document keyword-versus-variable rules |
| 4A | The formula editor includes the preview panel from 4D |
| 5A | Tokenizer matches declared variable names longest-first; reports "undeclared name" with suggestions |
| 5B | Algorithm parser recognises keywords only at statement start and warns on keyword-named variables |
| 6A | Translator emits floor division for the "round down" template and records result type |
| 12A | Add fixtures for binary search, bubble sort, average of array, and power by squaring |

## Additional Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Users misread precedence | High | Rendered form, parenthesised view, numeric preview, "Did you mean" hint |
| Multi-letter names split into letters | High | Variable-aware tokenizer; variable picker; warning for undeclared names |
| Keyword clashes (`end`, `start`) | Medium | Rename suggestions; keywords only at statement start |
| Auto-conversion changes a formula unexpectedly | Medium | Never auto-edit silently; show suggestion and require a click |
| Explanation text wrong or misleading | Medium | Generated from AST by rules; unit-tested; AI explanation labelled separately |

## Updated Definition of Done (additions)

- Each formula shows rendered maths, a plain-English reading, target-language code, and a type check.
- Declared multi-letter variables are always recognised as one name.
- Common precedence mistakes are visible and come with a suggested fix.
- The textbook view of the algorithm matches the text.

## Updated Weekly Schedule (changes)

- **Week 3:** Phases 4B, 4C, 4D
- **Week 4:** Phases 5, 5A, 5D, 5E
- **Week 5:** Phases 5B, 5C, 5F
- Remaining weeks shift by about one week; total about 12 weeks part-time including buffer.
