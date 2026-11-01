# FlowCode — Flowchart-to-Code Generator

A web application where users design an algorithm as a flowchart by dragging and dropping components (Start, Input, Process, Decision, Loop, Output, End), naming them, and selecting a programming language. A local or online AI model then generates code that follows the flowchart's logic.

---

## 1. Project Overview

### 1.1 Idea
Users build algorithms visually instead of writing code. The application converts the diagram into a structured, language-independent representation (JSON), validates it, and asks an AI model (or deterministic templates) to produce code in the chosen language (Python first; Java, C++, and others later).

### 1.2 Example
Flowchart:

```
Start
  |
Input: Enter number n
  |
Decision: Is n % 2 == 0?
  |-- Yes --> Print "Even" --\
  |-- No  --> Print "Odd"  --+--> End
```

Generated Python:

```python
n = int(input("Enter number n: "))
if n % 2 == 0:
    print("Even")
else:
    print("Odd")
```

### 1.3 Key Differentiator
The core value is **reliable conversion of an editable flowchart into executable code**, not just an AI chat interface. The AI receives the algorithm's logic (nodes, properties, connections, execution order), never a screenshot. Visual coordinates are not part of the algorithm.

### 1.4 Concepts Covered (academic value)
Visual programming, graph representation and traversal, compiler-style intermediate representation, AI/LLM integration, code validation, sandboxed execution, and software testing.

---

## 2. Processing Pipeline

| Step | Stage | Description |
|------|-------|-------------|
| 1 | Visual Flowchart Editor | User creates and connects blocks |
| 2 | Graph Validator | Detects missing connections, invalid conditions, bad loops |
| 3 | Structured Algorithm Representation | Diagram converted to a standardized JSON (intermediate representation) |
| 4 | AI Code Generation Engine | Algorithm JSON + selected language -> generated code |
| 5 | Code Validation & Testing | Syntax check and permitted tests run in isolation |
| 6 | Code Editor & Results | Displays code, errors, explanations, and output |

```
Browser (HTML/CSS/JS + Drawflow)
        |  fetch() JSON over HTTP
        v
Flask backend
  -> flow_validator  -> code_generator (templates) -> ai_provider (Ollama / online API)
  -> syntax check / sandboxed test run
        |
        v
Generated code returned as JSON and shown in the UI
```

---

## 3. Intermediate Representation (JSON)

Use JSON as the intermediate representation. Example for the even/odd flowchart:

```json
{
  "language": "python",
  "nodes": [
    {"id": "n1", "type": "input", "variable": "number"},
    {"id": "n2", "type": "decision", "condition": "number % 2 == 0"},
    {"id": "n3", "type": "output", "value": "\"Even\""},
    {"id": "n4", "type": "output", "value": "\"Odd\""}
  ],
  "edges": [
    {"source": "n1", "target": "n2"},
    {"source": "n2", "sourceHandle": "true",  "target": "n3"},
    {"source": "n2", "sourceHandle": "false", "target": "n4"}
  ]
}
```

This is simplified. The final schema should also define:
- Start/End nodes and node ordering
- Variable types where needed
- How loop conditions are evaluated and where execution returns
- How true/false branches are represented (`sourceHandle`)
- Rules for valid variable names and supported expressions

Models/APIs supporting constrained (structured) output help keep the representation consistent.

---

## 4. Technology Stack

| Layer | Choice | Purpose |
|-------|--------|---------|
| Frontend | HTML + CSS + JavaScript (vanilla) | Structure, styling, interactivity (dragging, connecting, clicks, requests) |
| Flowchart editor | Drawflow | Draggable nodes, ports, connections, import/export of diagram JSON |
| Backend | Python + Flask | Receives diagram JSON, validates, calls AI, returns code |
| AI | Ollama (local) or online API | Code generation from structured algorithm |
| Storage | SQLite | Projects, diagrams, selected language, generated code |
| Optional | Monaco Editor | Professional code editor panel (a plain textarea is fine for a prototype) |

No React is required; vanilla JS + Flask + Drawflow is enough for version 1. JavaScript is required because CSS cannot implement interactive flowchart behavior.

### Local vs Online AI

**Option A — Local (Ollama + a coding model)**
- Pros: privacy, offline use after setup, no per-request cost.
- Cons: hardware/memory requirements, slower, smaller models may give weaker results.

**Option B — Online (hosted model API)**
- Pros: capable models without local hardware.
- Cons: usage cost, rate limits, internet dependency, diagram data sent to a provider.

**Recommendation:** build a provider-independent AI service so the user can pick local or online in settings. The editor and workflow must not depend on a specific model.

---

## 5. Project Structure

```
flowcode/
├── app.py
├── requirements.txt
├── templates/
│   └── index.html
├── static/
│   ├── css/style.css
│   ├── js/
│   │   ├── flowchart.js
│   │   ├── editor.js
│   │   └── api.js
│   └── images/
├── services/
│   ├── flow_validator.py
│   ├── code_generator.py
│   └── ai_provider.py
├── database/
│   └── projects.db
└── tests/
    └── test_generator.py
```

- `flow_validator.py` — graph checks and traversal.
- `code_generator.py` — deterministic templates for basic constructs.
- `ai_provider.py` — abstraction over Ollama and online providers.

---

## 6. Features

### Version 1 (focused demo)
- **Visual designer:** Start, End, Input, Output, Process, Decision, Loop blocks; users set variable names, expressions, conditions, labels.
- **AI code generation:** Python first; show result and allow editing.
- **Validation & debugging:** highlight disconnected blocks, missing decision branches, invalid expressions, incorrectly constructed loops.
- **Save & export:** save diagrams, copy code, download source files, reopen projects.

### Later versions
Java and C++ support, natural-language-to-flowchart, flowchart-to-pseudocode, execution tracing, automatic test-case generation, AI-assisted debugging.

---

## 7. Challenges and Mitigations

- **Representing logic correctly** is harder than integrating AI. Decision nodes need explicit true/false paths; loops need defined condition placement and return point; variables need valid names; expressions must be interpreted consistently.
- **Generated code is not guaranteed correct.** Syntax-check it and test against expected outputs.
- **Security:** never execute generated code directly on the main server. Use an isolated environment (container/subprocess) with time, memory, and no-network limits.
- **Hybrid approach (recommended):** deterministic templates for basic constructs (input, output, if/else, loops); AI for complex expressions, language conversion, explanations, and debugging. This gives predictable results.

---

## 8. Development Roadmap

| Phase | Deliverable |
|-------|-------------|
| 1 | Drag-and-drop canvas with editable blocks (three-panel UI) |
| 2 | Store nodes and connections in a structured graph |
| 3 | Graph validation and algorithm traversal |
| 4 | Working Python code from simple diagrams |
| 5 | Integrate one local or online AI model |
| 6 | Code editing, testing, error display, project saving |
| 7 | More languages and UI polish |

### Suggested build order
1. Three-panel interface in HTML/CSS (blocks palette | canvas | code/output).
2. Integrate Drawflow and implement the flowchart components.
3. JavaScript for editing node properties and exporting diagram JSON.
4. Flask endpoints to receive and validate the diagram.
5. Connect one AI model and generate Python code.
6. Display generated code in the UI.
7. Add SQLite saving and optional safe code execution.

### First milestone
Design an algorithm -> generate Python -> run against a test case -> show the result. Expand to more languages only after this works reliably.

---

## 9. Proposed API Endpoints (draft)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/validate` | Validate diagram JSON, return errors/warnings |
| POST | `/api/generate` | Generate code for diagram + language |
| POST | `/api/run` | Run code with test input in sandbox (optional) |
| GET/POST | `/api/projects` | List / save projects |
| GET/PUT/DELETE | `/api/projects/<id>` | Load / update / delete project |
| GET/POST | `/api/settings` | Select AI provider and model |

## 10. Draft Data Model (SQLite)

`projects(id, name, language, diagram_json, generated_code, created_at, updated_at)`

---

## 11. Getting Started (planned)

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install flask requests
# Local AI (optional): install Ollama and pull a coding model
python app.py
```

Open `http://127.0.0.1:5000`.

---

## 12. Verdict
A strong student project: it blends visual programming, graph processing, compiler concepts, AI integration, and testing. Best suited to someone who already knows Python, HTML, and CSS and is willing to learn JavaScript.


---

# 13. Update: Algorithm Mode and Mathematical Formula Support

This section extends the project. Users are no longer limited to drawing a flowchart. They can also **write the algorithm as text** and use **mathematical formulas in proper mathematical notation** (fractions, powers, square roots, summations, and so on) inside either mode. Both modes feed the same pipeline.

## 13.1 Input Modes

| Mode | What the user does | Result |
|------|--------------------|--------|
| Flowchart mode | Drag and drop blocks, name them, connect them | Diagram -> IR (JSON) |
| Algorithm mode | Type structured pseudocode in a text editor | Parsed -> IR (JSON) |
| Describe mode (optional, AI) | Write the idea in plain English | AI drafts pseudocode, user reviews, then parsed -> IR |

All three modes converge on **one IR**, so validation, code generation, testing, and saving work identically regardless of how the algorithm was entered.

```
Flowchart editor ----\
Algorithm text -------+--> IR (JSON) --> Validator --> Code generator / AI --> Code
Plain English (AI) --/
```

### Two-way synchronization
- **Algorithm -> Flowchart:** typing or editing the algorithm auto-generates and lays out the flowchart.
- **Flowchart -> Algorithm:** drawing a flowchart shows its algorithm text live.
- Both are views of one IR; the user can switch modes without losing work.

## 13.2 Algorithm Text Syntax

A fixed, simple pseudocode grammar keeps parsing deterministic (the AI is not needed to understand it). Keywords are case-insensitive.

| Construct | Syntax |
|-----------|--------|
| Start / end | `START` ... `END` |
| Input | `INPUT n` or `INPUT n : int "Enter number"` |
| Assignment | `SET x = expression` (also `x <- expression` or `x ← expression`) |
| Output | `PRINT expression` |
| Decision | `IF condition THEN` ... `ELSE` ... `END IF` |
| While loop | `WHILE condition DO` ... `END WHILE` |
| For loop | `FOR i FROM 1 TO n [STEP 1] DO` ... `END FOR` |
| Comment | `// text` |

### Example 1 — Even or odd
```
START
INPUT n : int "Enter number n"
IF n mod 2 = 0 THEN
    PRINT "Even"
ELSE
    PRINT "Odd"
END IF
END
```

### Example 2 — Quadratic equation (with formulas)
```
START
INPUT a, b, c : float
SET D = $b^{2} - 4ac$
IF D < 0 THEN
    PRINT "No real roots"
ELSE
    SET x1 = $\frac{-b + \sqrt{D}}{2a}$
    SET x2 = $\frac{-b - \sqrt{D}}{2a}$
    PRINT x1, x2
END IF
END
```

Formulas are wrapped in `$ ... $` (LaTeX), or the user can type ordinary text expressions (`b^2 - 4*a*c`). Both are accepted and stored in the same form.

## 13.3 Mathematical Formula Support

### Goals
- Users write formulas the way they appear in a textbook, not in code syntax.
- Formulas are displayed rendered (for example, a real fraction bar and a square-root sign) in the algorithm view and on flowchart blocks.
- Each formula is converted into correct code for the chosen language.

### Recommended tools
| Purpose | Tool |
|---------|------|
| Visual math input field (type or click symbols, get LaTeX) | MathLive (`<math-field>`) |
| Render formulas on the page | KaTeX |
| Convert math to a structured tree (MathJSON) | MathLive / Compute Engine |
| Backend validation and symbolic checks (optional) | SymPy |

Exact APIs should be verified against each library's documentation when implementing. The design does not depend on one library: the stored contract is the formula **AST** described below.

### Supported notation

| Mathematical notation | LaTeX input | Python | Java | C++ |
|-----------------------|-------------|--------|------|-----|
| Addition, subtraction | `a + b`, `a - b` | `a + b` | `a + b` | `a + b` |
| Multiplication | `a \times b`, `ab`, `a \cdot b` | `a * b` | `a * b` | `a * b` |
| Division (real) | `\frac{a}{b}` | `(a) / (b)` | `(double)(a) / (b)` | `(double)(a) / (b)` |
| Integer division | `\lfloor \frac{a}{b} \rfloor` | `a // b` | `a / b` (ints) | `a / b` (ints) |
| Remainder | `a \bmod b` | `a % b` | `a % b` | `a % b` |
| Power | `x^{n}` | `x ** n` | `Math.pow(x, n)` | `pow(x, n)` |
| Square root | `\sqrt{x}` | `math.sqrt(x)` | `Math.sqrt(x)` | `sqrt(x)` |
| n-th root | `\sqrt[n]{x}` | `x ** (1/n)` | `Math.pow(x, 1.0/n)` | `pow(x, 1.0/n)` |
| Absolute value | `\left| x \right|` | `abs(x)` | `Math.abs(x)` | `fabs(x)` |
| Floor / ceiling | `\lfloor x \rfloor`, `\lceil x \rceil` | `math.floor(x)` | `Math.floor(x)` | `floor(x)` |
| Factorial | `n!` | `math.factorial(n)` | helper function | helper function |
| Trigonometry | `\sin x`, `\cos x`, `\tan x` | `math.sin(x)` | `Math.sin(x)` | `sin(x)` |
| Logarithm | `\ln x`, `\log_{10} x`, `\log_{b} x` | `math.log(x)` | `Math.log(x)` | `log(x)` |
| Exponential | `e^{x}` | `math.exp(x)` | `Math.exp(x)` | `exp(x)` |
| Constants | `\pi`, `e` | `math.pi`, `math.e` | `Math.PI`, `Math.E` | `M_PI`, `M_E` |
| Summation | `\sum_{i=1}^{n} f(i)` | loop accumulator | loop accumulator | loop accumulator |
| Product | `\prod_{i=1}^{n} f(i)` | loop accumulator | loop accumulator | loop accumulator |
| Binomial | `\binom{n}{k}` | `math.comb(n, k)` | helper function | helper function |
| Min / max | `\min(a,b)`, `\max(a,b)` | `min(a, b)` | `Math.min(a, b)` | `std::min(a, b)` |
| GCD | `\gcd(a,b)` | `math.gcd(a, b)` | helper function | `std::gcd(a, b)` |
| Subscripts | `x_{1}`, `a_{i}` | `x1` / `a[i]` | `x1` / `a[i]` | `x1` / `a[i]` |
| Comparisons | `<`, `>`, `\le`, `\ge`, `\ne`, `=` | `<`, `>`, `<=`, `>=`, `!=`, `==` | same | same |
| Logic | `\land`, `\lor`, `\lnot` | `and`, `or`, `not` | `&&`, `||`, `!` | `&&`, `||`, `!` |

Notes:
- `Summation` and `product` have no direct operator in these languages, so the generator emits a loop that accumulates the result (or `sum(...)` in Python).
- In Java and C++, `Math`/`<cmath>` imports and helper functions (factorial, binomial) are added automatically only when used.
- In algorithm mode, `=` inside `IF`/`WHILE` conditions means comparison; assignments use `SET`, `<-`, or `←`.

### Precedence and semantics (fixed rules)
1. Parentheses and grouping, then functions, then exponent, then unary minus, then multiplication/division/mod, then addition/subtraction, then comparison, then `not`, `and`, `or`.
2. `\frac{a}{b}` is **real division**. Integer division must be written explicitly with floor, so results never silently change between languages.
3. Implicit multiplication (`4ac`, `2a`) is allowed but each multi-letter variable name is ambiguous, so the editor resolves it using declared variables (a, b, c are known single letters). Names such as `rate` or `total` should be written with `\text{rate}` or in text mode, and the validator warns on ambiguity.
4. Types: `int`, `float`, `string`, `bool`. Results of `\sqrt`, `\sin`, `\log`, `\frac` are `float`.

## 13.4 Formula Representation in the IR

Every expression field (`condition`, `value`, `expression`) can now be an object so the original math, its text form, and its parsed tree are all kept:

```json
{
  "id": "n3",
  "type": "process",
  "variable": "x1",
  "expression": {
    "latex": "\\frac{-b + \\sqrt{D}}{2a}",
    "text": "(-b + sqrt(D)) / (2*a)",
    "ast": {
      "op": "div",
      "args": [
        {"op": "add", "args": [{"op": "neg", "args": [{"var": "b"}]},
                               {"op": "sqrt", "args": [{"var": "D"}]}]},
        {"op": "mul", "args": [{"num": 2}, {"var": "a"}]}
      ]
    }
  }
}
```

- `latex` is shown to the user (rendered with KaTeX).
- `ast` is what the code generator and validator use. This makes translation to each language **deterministic** rather than depending on the AI.
- The top-level IR also records `"mode": "flowchart" | "algorithm"` and, for algorithm mode, the original `"source_text"` so it can be restored exactly.

## 13.5 Validation Added for Algorithm Mode and Formulas

- Algorithm text: syntax errors reported with line and column (missing `END IF`, unknown keyword, unbalanced parentheses).
- Formula: unbalanced braces, unknown function or symbol, unsupported notation.
- Variables used in a formula must be defined earlier (data-flow check).
- Domain warnings: possible division by zero, square root of a possibly negative value, `log` of a non-positive value, factorial of a negative or non-integer.
- Type warnings: using a `string` in arithmetic; float used where an integer is required (loop counters, `mod`).
- Ambiguity warnings: implicit multiplication of multi-letter names.

## 13.6 Role of the AI With Formulas

1. **Deterministic first:** the AST is translated to code by rule. This gives exact, testable formulas.
2. **AI for the rest:** AI handles surrounding structure, language idioms, explanation, and optional conversion of plain-English or handwritten-style math into LaTeX/pseudocode, always shown to the user for confirmation before use.
3. **Cross-check:** generated code is run on test inputs and compared with a result computed from the AST in Python (or SymPy). Mismatches are flagged.

## 13.7 Updated UI

- Mode switcher: **Flowchart | Algorithm | Split view** (both side by side, synchronized).
- Algorithm editor with line numbers, keyword highlighting, and error markers.
- Formula editor: a math field (WYSIWYG) with a symbol toolbar (fraction, power, root, sum, product, pi, comparison, logic), plus a LaTeX text toggle.
- Rendered math in the Properties panel, on flowchart blocks, and in the read-only algorithm preview.
- Example gallery with math-heavy algorithms (below).

## 13.8 Example Algorithms for Demos and Tests

| Algorithm | Key formula (LaTeX) |
|-----------|--------------------|
| Even or odd | `n \bmod 2 = 0` |
| Area of circle | `A = \pi r^{2}` |
| Quadratic roots | `x = \frac{-b \pm \sqrt{b^{2}-4ac}}{2a}` (split into two assignments) |
| Distance between two points | `d = \sqrt{(x_2-x_1)^{2} + (y_2-y_1)^{2}}` |
| Compound interest | `A = P\left(1+\frac{r}{n}\right)^{nt}` |
| Sum of first n numbers | `S = \sum_{i=1}^{n} i` (also `\frac{n(n+1)}{2}` to cross-check) |
| Factorial | `n! = \prod_{i=1}^{n} i` |
| Average of marks | `\text{avg} = \frac{1}{n}\sum_{i=1}^{n} m_i` |
| GCD (Euclid) | loop with `a \bmod b` |
| Temperature conversion | `F = \frac{9}{5}C + 32` |

Note: the symbol `\pm` is not a single value, so the editor expands it into two separate assignments (one with `+`, one with `-`) instead of treating it as an operator.

## 13.9 Updated Project Structure (additions)

```
services/
├── algorithm_parser.py      # pseudocode text -> IR
├── algorithm_printer.py     # IR -> pseudocode text
├── expression_parser.py     # LaTeX/text -> AST
├── expression_translator.py # AST -> Python / Java / C++ expression
static/js/
├── algorithm_editor.js      # text editor, highlighting, errors
├── formula_editor.js        # MathLive integration, symbol toolbar
├── mode_sync.js             # flowchart <-> algorithm synchronization
tests/
├── test_algorithm_parser.py
├── test_expression_translator.py
docs/
├── algorithm_grammar.md
├── formula_support.md
```

## 13.10 New Limitations to Document
- Only the listed notation is supported; unsupported symbols produce a clear error, not a guess.
- Algorithm text must follow the defined grammar; free-form English goes through the optional AI "Describe" mode with user confirmation.
- Auto-layout of a flowchart generated from text may need manual tidying.
- Floating-point results can differ slightly between languages, so tests compare with a tolerance.


---

# 14. Update: Word-Style Formula Template Gallery

Based on the Microsoft Word equation ribbon screenshots, the formula editor will offer **ready-made structure templates** in the same grouping: the user clicks a template (for example a stacked fraction), it is inserted with empty boxes (placeholders), and the user fills the boxes. No LaTeX knowledge is required.

## 14.1 Ribbon Layout (mirrors Word)

| Ribbon button | Gallery groups (as in the screenshots) |
|---------------|----------------------------------------|
| Fraction | Fraction; Common Fraction |
| Script | Subscripts and Superscripts; Common Subscripts and Superscripts |
| Radical | Radicals; Common Radicals |
| Integral | Integrals; Contour Integrals |
| Large Operator | Summations; Products and Co-Products; Unions and Intersections; Other Large Operators |
| Bracket | Parentheses, brackets, braces, absolute value, floor/ceiling, cases (not shown in the screenshots; added for completeness) |
| Function | Functions (log, lim, min, max, ln); Common Functions; trigonometric functions |
| Accent | Hat, bar, vector, dot (not shown in the screenshots; added for completeness) |
| Operator | Basic Operators; Operator Structures; Common Operator Structures |
| Matrix | Empty Matrices; Dots; Identity Matrices; Matrices with Brackets; Sparse Matrices |

Interaction:
- Click a template to insert it at the cursor. If text is selected, it is placed in the first box.
- `Tab` / `Shift+Tab` moves between boxes. `Esc` leaves the structure.
- Typing a shortcut works too: `\frac`, `\sqrt`, `\sum`, or `/` after a term makes a fraction.
- Every template shows a status badge: **Runs** (code is generated), **Approximate** (numeric result with a warning), or **Display only** (shown and saved, but no code is generated).
- A "Recently used" row appears at the top of the gallery.

## 14.2 Template Catalogue

`□` marks an empty box. LaTeX shown is the stored form. Status: **R** = Runs, **A** = Approximate (numeric), **D** = Display only.

### Fraction
| Template | LaTeX | Meaning | Status |
|----------|-------|---------|--------|
| Stacked fraction | `\frac{□}{□}` | real division | R |
| Skewed fraction | `{}^{□}\!/\!{}_{□}` | real division | R |
| Linear fraction | `□/□` | real division | R |
| Small stacked fraction | `\tfrac{□}{□}` | real division | R |
| dy/dx | `\frac{\mathrm{d}y}{\mathrm{d}x}` | derivative of y | A (numeric derivative) |
| Δy/Δx | `\frac{\Delta y}{\Delta x}` | ratio of variables `delta_y`, `delta_x` | R |
| ∂y/∂x | `\frac{\partial y}{\partial x}` | partial derivative | D |
| δy/δx | `\frac{\delta y}{\delta x}` | ratio of variables `dlt_y`, `dlt_x` | R |
| π/2 | `\frac{\pi}{2}` | constant expression | R |

Note: `dy/dx` is only treated as a derivative when inserted from the template (upright `\mathrm{d}`); typed ordinary `d*y/d*x` stays plain multiplication to avoid ambiguity.

### Script
| Template | LaTeX | Meaning | Status |
|----------|-------|---------|--------|
| Superscript | `□^{□}` | power | R |
| Subscript | `□_{□}` | indexed or subscripted name (`x_1` -> `x1`, `a_i` -> `a[i]`) | R |
| Subscript and superscript | `□_{□}^{□}` | power of a subscripted name | R |
| Left sub-superscript | `{}_{□}^{□}□` | pre-scripts (tensor/nuclear notation) | D |
| x with nested script | `x_{y^{2}}` | subscript must be a name or integer; nested powers rejected with a message | D |
| e to an expression | `e^{-i\omega t}` | real case `e^{-x}` runs; imaginary unit `i` needs complex numbers | R (real) / D (complex) |
| x squared | `x^{2}` | power | R |
| Pre-scripted Y | `{}_{1}^{n}Y` | pre-scripts | D |

### Radical
| Template | LaTeX | Meaning | Status |
|----------|-------|---------|--------|
| Square root | `\sqrt{□}` | square root | R |
| n-th root | `\sqrt[□]{□}` | root of degree n | R |
| Square root (degree 2) | `\sqrt[2]{□}` | square root | R |
| Cube root | `\sqrt[3]{□}` | cube root (negative inputs handled with sign rule) | R |
| Quadratic formula | `\frac{-b \pm \sqrt{b^{2}-4ac}}{2a}` | expands into two assignments (`+` and `-`) | R |
| Pythagorean | `\sqrt{a^{2}+b^{2}}` | hypotenuse | R |

### Integral
Each of the families below comes in three forms: no limits, side limits (`\int_{a}^{b}`), and stacked limits (`\int\limits_{a}^{b}`).

| Family | LaTeX symbol | Status |
|--------|--------------|--------|
| Single integral | `\int` | A for a definite integral `\int_{a}^{b} f(x)\,\mathrm{d}x` (composite Simpson's rule, default 1000 steps; warning shown). Indefinite integral: D |
| Double integral | `\iint` | A (nested numeric, rectangular limits) in a later version; D in v1 |
| Triple integral | `\iiint` | D in v1 |
| Contour integral | `\oint` | D |
| Surface integral | `\oiint` | D |
| Volume integral | `\oiiint` | D |

Rendering of some contour/surface symbols may need a fallback glyph depending on the math library; check during implementation.

### Large Operators
| Group | Templates (LaTeX) | Status |
|-------|-------------------|--------|
| Summations (5 limit layouts) | `\sum □`, `\sum_{i=a}^{b} □` (under/over), side limits, under only `\sum_{i \in S} □` | R for numeric limits (loop accumulator); under-only over a set/condition: A/later |
| Products | `\prod_{i=a}^{b} □` (5 layouts) | R |
| Co-products | `\coprod` | D |
| Unions | `\bigcup_{i=a}^{b} □` | R later (set union in Python `set`, Java `Set`, C++ `std::set`) |
| Intersections | `\bigcap_{i=a}^{b} □` | R later (set intersection) |
| Big OR / AND | `\bigvee`, `\bigwedge` | R (generated as `any(...)` / `all(...)` loops) |

### Function
| Template | LaTeX | Status |
|----------|-------|--------|
| Logarithm with base | `\log_{□} □` | R |
| Logarithm (base 10) | `\log □` | R |
| Natural logarithm | `\ln □` | R |
| Limit | `\lim_{□ \to □} □` | A (evaluated numerically near the point, with a warning) or D |
| Minimum | `\min_{□} □` | R when the range is discrete (e.g. `\min_{1 \le i \le n} a_i`); continuous range: D |
| Maximum | `\max_{□} □` | same as minimum |
| Limit of (1+1/n)^n | `\lim_{n\to\infty}\left(1+\frac{1}{n}\right)^{n}` | A or D |
| Maximum over a range | `\max_{0\le x \le 1} x e^{-x^{2}}` | A (grid search with warning) or D |
| Trigonometric | `\sin □`, `\cos □`, `\tan □`, `\sec □`, `\csc □`, `\cot □`, inverse and hyperbolic versions | R (angles in radians; degree option available) |

### Bracket (additional)
| Template | LaTeX | Status |
|----------|-------|--------|
| Parentheses | `\left( □ \right)` | R |
| Square brackets | `\left[ □ \right]` | R (grouping or index) |
| Braces | `\left\{ □ \right\}` | R (grouping; set literal later) |
| Absolute value | `\left| □ \right|` | R |
| Floor / ceiling | `\lfloor □ \rfloor`, `\lceil □ \rceil` | R |
| Norm | `\left\| □ \right\|` | D (until vectors are supported) |
| Cases (piecewise) | `\begin{cases} □ & □ \\ □ & □ \end{cases}` | R later (generated as if/else expression) |

### Accent (additional)
| Template | LaTeX | Meaning | Status |
|----------|-------|---------|--------|
| Bar | `\bar{x}` | decorated variable name `x_bar` (for example the mean) | R |
| Hat | `\hat{x}` | variable name `x_hat` | R |
| Vector | `\vec{v}` | variable name `v_vec` | R |
| Dot | `\dot{x}` | variable name `x_dot` | R |

### Operator
| Template | LaTeX | Meaning | Status |
|----------|-------|---------|--------|
| Colon-equals | `:=` | assignment (same as `SET`) | R |
| Double equals | `==` | equality comparison | R |
| Plus-equals | `+=` | compound assignment | R |
| Minus-equals | `-=` | compound assignment | R |
| Equals by definition | `\stackrel{\text{def}}{=}` | definition, treated as assignment | R |
| Measured-by equals | `\stackrel{\text{m}}{=}` | annotation | D |
| Delta-equals | `\stackrel{\Delta}{=}` | annotation | D |
| Arrows with labels | `\xleftarrow{□}`, `\xrightarrow{□}`, `\xLeftarrow{□}`, `\xRightarrow{□}`, `\xleftrightarrow{□}`, `\xLeftrightarrow{□}` (text above or below) | annotation; `←` alone is assignment | D |
| Yields | `\xrightarrow{\text{yields}}` | annotation | D |
| Delta over arrow | `\xrightarrow{\Delta}` | annotation | D |

### Matrix
| Group | Templates | Status |
|-------|-----------|--------|
| Empty matrices | 1x2, 2x1, 1x3, 3x1, 2x2, 2x3, 3x2, 3x3 boxes; rows/columns can be added or removed | R later (2D arrays) |
| Dots | `\cdots`, `\ldots`, `\vdots`, `\ddots` | D (layout symbols) |
| Identity matrices | 2x2, 3x3 (full and sparse display) `\begin{pmatrix}1&0\\0&1\end{pmatrix}` | R later (`identity(n)`) |
| Matrices with brackets | `pmatrix` `( )`, `bmatrix` `[ ]`, `vmatrix` `\| \|` (determinant), `Bmatrix` `{ }`, `Vmatrix` `\|\| \|\|` | R later |
| Sparse matrices | matrices with blank cells meaning zero | R later |

Matrix operations planned for the later version: addition, subtraction, scalar multiplication, matrix product, transpose `A^{T}`, determinant `\det A` or `|A|`, inverse `A^{-1}`; each translates to a generated helper function (nested loops) in Python, Java, and C++. The first release only stores and renders matrices.

## 14.3 Status Tiers (what the code generator can do)

| Tier | Meaning | Templates |
|------|---------|-----------|
| 1 - Runs (version 1) | Exact, deterministic translation | fractions, scripts (power, index), radicals, sum, product with numeric limits, big AND/OR, brackets/abs/floor/ceiling, log/ln/trig, min/max over discrete ranges, accents, `:=`, `+=`, `-=`, `==` |
| 2 - Approximate or later | Needs numeric methods or extra data types | definite integral, derivative, limit, continuous max/min, double integral, set union/intersection, cases, matrices and matrix operations, complex numbers |
| 3 - Display only | Shown and saved, but no code is generated | (remaining content after this point needs to be restored from your backup) |
