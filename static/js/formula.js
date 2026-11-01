/* Formula helper: a Word-style insert ribbon (galleries of ready-made structures with empty
 * boxes) and a live preview that shows the typed formula as real maths, in plain English,
 * and as the code it becomes. Formulas stay ordinary text; the ribbon only types for you. */
const Formula = (() => {
  const BOX = "\u25a1";
  const B = "\\square";

  /* Each item: text inserted into the field (box = empty slot) and the LaTeX used to draw its tile. */
  const CATALOGUE = [
    { id: "fraction", label: "Fraction", icon: "\\frac{x}{y}", groups: [
      { title: "Fraction", items: [
        { name: "Fraction", text: `(${BOX}) / (${BOX})`, latex: `\\frac{${B}}{${B}}` },
        { name: "Whole-number division (rounds down)", text: `(${BOX}) div (${BOX})`, latex: `\\left\\lfloor\\frac{${B}}{${B}}\\right\\rfloor` },
        { name: "Remainder", text: `(${BOX}) mod (${BOX})`, latex: `${B}\\bmod ${B}` },
      ] },
      { title: "Common fractions", items: [
        { name: "Average of two numbers", text: `(${BOX} + ${BOX}) / 2`, latex: `\\frac{${B}+${B}}{2}` },
        { name: "Middle position", text: `(${BOX} + ${BOX}) div 2`, latex: `\\left\\lfloor\\frac{${B}+${B}}{2}\\right\\rfloor` },
        { name: "Percentage", text: `${BOX} / ${BOX} * 100`, latex: `\\frac{${B}}{${B}}\\cdot 100` },
        { name: "Half of a value", text: `${BOX} / 2`, latex: `\\frac{${B}}{2}` },
      ] },
    ] },
    { id: "script", label: "Script", icon: "e^{x}", groups: [
      { title: "Powers and positions", items: [
        { name: "Power", text: `(${BOX})^(${BOX})`, latex: `${B}^{${B}}` },
        { name: "Squared", text: `(${BOX})^2`, latex: `${B}^{2}` },
        { name: "Cubed", text: `(${BOX})^3`, latex: `${B}^{3}` },
        { name: "e to the power", text: `exp(${BOX})`, latex: `e^{${B}}` },
        { name: "Item of a list", text: `${BOX}[${BOX}]`, latex: `${B}_{${B}}` },
        { name: "Next item", text: `${BOX}[${BOX} + 1]`, latex: `${B}_{${B}+1}` },
        { name: "Previous item", text: `${BOX}[${BOX} - 1]`, latex: `${B}_{${B}-1}` },
      ] },
    ] },
    { id: "radical", label: "Radical", icon: "\\sqrt[n]{x}", groups: [
      { title: "Radicals", items: [
        { name: "Square root", text: `sqrt(${BOX})`, latex: `\\sqrt{${B}}` },
        { name: "Cube root", text: `(${BOX})^(1/3)`, latex: `\\sqrt[3]{${B}}` },
        { name: "Root of any degree", text: `(${BOX})^(1/${BOX})`, latex: `\\sqrt[${B}]{${B}}` },
      ] },
      { title: "Common radicals", items: [
        { name: "Quadratic formula (plus)", text: "(-b + sqrt(b^2 - 4*a*c)) / (2*a)", latex: "\\frac{-b+\\sqrt{b^{2}-4ac}}{2a}" },
        { name: "Quadratic formula (minus)", text: "(-b - sqrt(b^2 - 4*a*c)) / (2*a)", latex: "\\frac{-b-\\sqrt{b^{2}-4ac}}{2a}" },
        { name: "Hypotenuse", text: `sqrt((${BOX})^2 + (${BOX})^2)`, latex: `\\sqrt{${B}^{2}+${B}^{2}}` },
        { name: "Distance between two points", text: "sqrt((x2 - x1)^2 + (y2 - y1)^2)", latex: "\\sqrt{(x_2-x_1)^2+(y_2-y_1)^2}" },
      ] },
    ] },
    { id: "operator", label: "Operator", icon: "\\sum_{i}^{n}", groups: [
      { title: "Summations and products", items: [
        { name: "Sum (sigma)", text: `Sum(i, 1, ${BOX}, ${BOX})`, latex: `\\sum_{i=1}^{${B}}${B}` },
        { name: "Product (pi)", text: `Prod(i, 1, ${BOX}, ${BOX})`, latex: `\\prod_{i=1}^{${B}}${B}` },
      ] },
      { title: "Common sums", items: [
        { name: "1 + 2 + ... + n", text: `Sum(i, 1, ${BOX}, i)`, latex: `\\sum_{i=1}^{${B}} i` },
        { name: "Sum of squares", text: `Sum(i, 1, ${BOX}, i^2)`, latex: `\\sum_{i=1}^{${B}} i^{2}` },
        { name: "Factorial as a product", text: `Prod(i, 1, ${BOX}, i)`, latex: `\\prod_{i=1}^{${B}} i` },
        { name: "Average of a list", text: `sum(${BOX}) / len(${BOX})`, latex: `\\frac{\\sum ${B}}{\\left|${B}\\right|}` },
      ] },
    ] },
    { id: "function", label: "Function", icon: "\\sin\\theta", groups: [
      { title: "Functions", items: [
        { name: "Absolute value", text: `abs(${BOX})`, latex: `\\left|${B}\\right|` },
        { name: "Round down", text: `floor(${BOX})`, latex: `\\lfloor ${B}\\rfloor` },
        { name: "Round up", text: `ceil(${BOX})`, latex: `\\lceil ${B}\\rceil` },
        { name: "Natural logarithm", text: `log(${BOX})`, latex: `\\ln ${B}` },
        { name: "Logarithm base 10", text: `log10(${BOX})`, latex: `\\log_{10} ${B}` },
        { name: "Logarithm with base", text: `log(${BOX}, ${BOX})`, latex: `\\log_{${B}} ${B}` },
        { name: "Smallest of", text: `min(${BOX}, ${BOX})`, latex: `\\min(${B},${B})` },
        { name: "Largest of", text: `max(${BOX}, ${BOX})`, latex: `\\max(${B},${B})` },
        { name: "Factorial", text: `factorial(${BOX})`, latex: `${B}!` },
        { name: "Greatest common divisor", text: `gcd(${BOX}, ${BOX})`, latex: `\\gcd(${B},${B})` },
      ] },
      { title: "Trigonometry (radians)", items: [
        { name: "Sine", text: `sin(${BOX})`, latex: `\\sin ${B}` },
        { name: "Cosine", text: `cos(${BOX})`, latex: `\\cos ${B}` },
        { name: "Tangent", text: `tan(${BOX})`, latex: `\\tan ${B}` },
        { name: "Pi", text: "pi", latex: "\\pi" },
        { name: "Circle area", text: `pi * (${BOX})^2`, latex: `\\pi ${B}^{2}` },
      ] },
    ] },
    { id: "compare", label: "Compare", icon: "a\\le b", groups: [
      { title: "Comparisons", items: [
        { name: "Equal to", text: `${BOX} = ${BOX}`, latex: `${B}=${B}` },
        { name: "Not equal to", text: `${BOX} != ${BOX}`, latex: `${B}\\ne ${B}` },
        { name: "Less than", text: `${BOX} < ${BOX}`, latex: `${B}<${B}` },
        { name: "Greater than", text: `${BOX} > ${BOX}`, latex: `${B}>${B}` },
        { name: "At most", text: `${BOX} <= ${BOX}`, latex: `${B}\\le ${B}` },
        { name: "At least", text: `${BOX} >= ${BOX}`, latex: `${B}\\ge ${B}` },
      ] },
      { title: "Logic and checks", items: [
        { name: "Both are true", text: `${BOX} and ${BOX}`, latex: `${B}\\;\\mathrm{and}\\;${B}` },
        { name: "Either is true", text: `${BOX} or ${BOX}`, latex: `${B}\\;\\mathrm{or}\\;${B}` },
        { name: "Not", text: `not ${BOX}`, latex: `\\lnot ${B}` },
        { name: "Is even", text: `${BOX} mod 2 = 0`, latex: `${B}\\bmod 2=0` },
        { name: "Is between", text: `${BOX} <= ${BOX} and ${BOX} <= ${BOX}`, latex: `${B}\\le ${B}\\;\\mathrm{and}\\;${B}\\le ${B}` },
        { name: "Brackets", text: `(${BOX})`, latex: `\\left(${B}\\right)` },
      ] },
    ] },
  ];

  const hasKatex = () => typeof katex !== "undefined";

  function renderMath(el, latex) {
    if (hasKatex()) {
      try { katex.render(latex, el, { throwOnError: false, strict: "ignore" }); return; } catch (err) { /* fall through */ }
    }
    el.textContent = latex;
  }

  /* ---------------- inserting ---------------- */
  function insertTemplate(el, text) {
    const start = el.selectionStart == null ? el.value.length : el.selectionStart;
    const end = el.selectionEnd == null ? start : el.selectionEnd;
    const selected = el.value.slice(start, end);
    const snippet = selected ? text.replace(BOX, () => selected) : text;
    el.value = el.value.slice(0, start) + snippet + el.value.slice(end);
    const rel = snippet.indexOf(BOX);
    el.focus();
    if (rel >= 0) el.setSelectionRange(start + rel, start + rel + 1);
    else el.setSelectionRange(start + snippet.length, start + snippet.length);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function enableBoxTab(el) {
    if (el.dataset.boxTab) return;
    el.dataset.boxTab = "1";
    el.addEventListener("keydown", (e) => {
      if (e.key !== "Tab" || e.shiftKey) return;
      const i = el.value.indexOf(BOX, el.selectionEnd);
      if (i >= 0) { e.preventDefault(); el.setSelectionRange(i, i + 1); }
    });
  }

  /* ---------------- gallery popup ---------------- */
  let popup = null, popupCleanup = null;

  function closeGallery() {
    if (popup) popup.remove();
    if (popupCleanup) popupCleanup();
    popup = popupCleanup = null;
  }

  function openGallery(button, category, getTarget, getWrap) {
    const same = popup && popup.dataset.cat === category.id;
    closeGallery();
    if (same) return;
    popup = document.createElement("div");
    popup.className = "fgal";
    popup.dataset.cat = category.id;
    popup.setAttribute("role", "dialog");
    popup.setAttribute("aria-label", category.label + " templates");
    category.groups.forEach((g) => {
      const title = document.createElement("div");
      title.className = "fgal-title";
      title.textContent = g.title;
      const grid = document.createElement("div");
      grid.className = "fgal-grid";
      g.items.forEach((item) => {
        const tile = document.createElement("button");
        tile.type = "button";
        tile.className = "ftile";
        tile.title = item.name;
        const math = document.createElement("span");
        math.className = "ftile-math";
        renderMath(math, item.latex);
        const cap = document.createElement("span");
        cap.className = "ftile-cap";
        cap.textContent = item.name;
        tile.append(math, cap);
        tile.addEventListener("click", () => {
          const wrap = getWrap ? getWrap() : "";
          insertTemplate(getTarget(), wrap + item.text + wrap);
          closeGallery();
        });
        grid.appendChild(tile);
      });
      popup.append(title, grid);
    });
    document.body.appendChild(popup);
    const r = button.getBoundingClientRect();
    const width = Math.min(380, window.innerWidth - 16);
    popup.style.width = width + "px";
    popup.style.left = Math.max(8, Math.min(r.left, window.innerWidth - width - 8)) + "px";
    popup.style.top = r.bottom + 4 + "px";
    popup.style.maxHeight = Math.max(160, window.innerHeight - r.bottom - 16) + "px";
    const onDown = (e) => { if (popup && !popup.contains(e.target) && !button.contains(e.target)) closeGallery(); };
    const onKey = (e) => { if (e.key === "Escape") { closeGallery(); button.focus(); } };
    setTimeout(() => document.addEventListener("mousedown", onDown), 0);
    document.addEventListener("keydown", onKey);
    popupCleanup = () => { document.removeEventListener("mousedown", onDown); document.removeEventListener("keydown", onKey); };
  }

  function buildRibbon(getTarget, getWrap) {
    const bar = document.createElement("div");
    bar.className = "fribbon";
    bar.setAttribute("role", "toolbar");
    bar.setAttribute("aria-label", "Insert a formula structure");
    CATALOGUE.forEach((cat) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "frib-btn";
      btn.title = cat.label;
      btn.setAttribute("aria-haspopup", "dialog");
      const icon = document.createElement("span");
      icon.className = "frib-icon";
      renderMath(icon, cat.icon);
      const label = document.createElement("span");
      label.className = "frib-label";
      label.textContent = cat.label + " \u25be";
      btn.append(icon, label);
      btn.addEventListener("mousedown", (e) => e.preventDefault());     // keep the caret in the field
      btn.addEventListener("click", () => openGallery(btn, cat, getTarget, getWrap));
      bar.appendChild(btn);
    });
    return bar;
  }

  /* ---------------- live preview ---------------- */
  function buildPreview(getKind, getVariables) {
    const box = document.createElement("div");
    box.className = "fpreview";
    box.hidden = true;
    box.innerHTML =
      '<div class="fp-note" hidden></div>' +
      '<div class="fp-math" aria-label="Formula as maths"></div>' +
      '<div class="fp-error" hidden></div>' +
      '<div class="fp-line fp-reading" hidden><b>Reads as:</b> <span></span></div>' +
      '<div class="fp-line fp-order" hidden><b>Order:</b> <code></code></div>' +
      '<div class="fp-line fp-code" hidden><b>Code:</b> <code></code> <span class="fp-type"></span></div>' +
      '<div class="fp-line fp-comment" hidden><b>In the code:</b><pre></pre></div>' +
      '<ul class="fp-notes"></ul>';
    const q = (s) => box.querySelector(s);
    let timer = null, seq = 0;

    function showNote(res) {
      box.hidden = false;
      ["fp-math", "fp-error", "fp-reading", "fp-order", "fp-code"].forEach((c) => { q("." + c).hidden = true; });
      const holder = q(".fp-note");
      holder.hidden = false;
      holder.innerHTML = "";
      res.segments.forEach((seg) => {
        const span = document.createElement("span");
        if (seg.text != null) {
          span.className = "fp-text";
          span.textContent = seg.text;
        } else if (seg.latex) {
          span.className = "fp-inline";
          renderMath(span, seg.latex);
        } else {
          span.className = "fp-inline-error";
          span.textContent = "$" + (seg.raw || "") + "$";
          span.title = seg.error;
        }
        holder.appendChild(span);
      });
      q(".fp-comment").hidden = false;
      q(".fp-comment pre").textContent = (res.comment || []).join("\n");
      const list = q(".fp-notes");
      list.innerHTML = "";
      (res.notes || []).forEach((n) => {
        const li = document.createElement("li");
        li.className = "fp-" + n.level;
        li.textContent = n.text;
        list.appendChild(li);
      });
    }

    function show(res) {
      if (res.kind === "note" && !res.empty) { showNote(res); return; }
      q(".fp-note").hidden = true;
      q(".fp-comment").hidden = true;
      const hasMath = res.ok && !res.empty;
      box.hidden = !!res.empty;
      if (res.empty) return;
      q(".fp-math").hidden = !hasMath;
      if (hasMath) renderMath(q(".fp-math"), res.latex);
      q(".fp-error").hidden = res.ok;
      q(".fp-error").textContent = res.ok ? "" : res.error;
      const set = (sel, value, textSel) => {
        const row = q(sel);
        row.hidden = !value;
        if (value) row.querySelector(textSel).textContent = value;
      };
      set(".fp-reading", res.ok ? res.reading : "", "span");
      set(".fp-order", res.ok ? res.ordered : "", "code");
      set(".fp-code", res.ok ? res.python : "", "code");
      q(".fp-type").textContent = res.ok && res.python ? "\u2192 " + res.type : "";
      const notes = q(".fp-notes");
      notes.innerHTML = "";
      (res.notes || []).forEach((n) => {
        const li = document.createElement("li");
        li.className = "fp-" + n.level;
        li.textContent = n.text;
        notes.appendChild(li);
      });
    }

    function update(text) {
      clearTimeout(timer);
      const mine = ++seq;
      if (!String(text || "").trim()) { show({ empty: true }); return; }
      timer = setTimeout(async () => {
        try {
          const res = await api.formulaPreview(text, getKind(), getVariables());
          if (mine === seq) show(res);
        } catch (err) {
          if (mine === seq) show({ ok: false, error: err.message });
        }
      }, 250);
    }
    return { el: box, update };
  }

  /* ---------------- public: properties panel ---------------- */
  /* fields: [{input, kind, anchor}] - preview is placed after `anchor`; the ribbon goes before the first anchor's row. */
  function attachToPanel(panel, fields, getVariables) {
    if (!fields.length) return;
    let active = fields[0];
    const ribbon = buildRibbon(() => active.input, () => (active.kind === "note" ? "$" : ""));
    panel.insertBefore(ribbon, fields[0].row);
    fields.forEach((f) => {
      enableBoxTab(f.input);
      f.input.addEventListener("focus", () => { active = f; });
      const preview = buildPreview(() => f.kind, getVariables);
      f.anchor.after(preview.el);
      f.input.addEventListener("input", () => preview.update(f.input.value));
      preview.update(f.input.value);
    });
  }

  /* ---------------- public: algorithm text area ---------------- */
  const LINE_PATTERNS = [
    [/^PRINT\s+(.+)$/i, "list"],
    [/^(?:ELSE\s+)?IF\s+(.+?)(?:\s+THEN)?$/i, "condition"],
    [/^WHILE\s+(.+?)(?:\s+DO)?$/i, "condition"],
    [/^(?:SET\s+)?[A-Za-z_]\w*(?:\[.+?\])?\s*(?:<-|\u2190|:=|(?<![=!<>])=(?!=))\s*(.+)$/i, "expression"],
  ];

  function formulaOfLine(line) {
    const s = line.trim();
    if (!s) return null;
    if (s.startsWith("//") || s.startsWith("#")) return { text: s.replace(/^(\/\/|#)\s?/, ""), kind: "note" };
    if (/^(INPUT|FOR|END|START|ELSE)\b/i.test(s) && !/^ELSE\s+IF\b/i.test(s)) return null;
    for (const [re, kind] of LINE_PATTERNS) {
      const m = re.exec(s);
      if (m) return { text: m[1], kind };
    }
    return null;
  }

  function variablesOfText(text) {
    const names = new Set();
    const add = (re) => { let m; while ((m = re.exec(text))) names.add(m[1]); };
    let m;
    const inputRe = /^\s*INPUT\s+([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)/gim;
    while ((m = inputRe.exec(text))) m[1].split(",").forEach((v) => names.add(v.trim()));
    add(/^\s*FOR\s+([A-Za-z_]\w*)/gim);
    add(/^\s*(?:SET\s+)?([A-Za-z_]\w*)\s*(?:<-|\u2190|:=|=(?!=))/gim);
    return Array.from(names);
  }

  function attachToTextarea(textarea, ribbonHost, previewHost) {
    const onCommentLine = () => {
      const lineIdx = textarea.value.slice(0, textarea.selectionStart).split("\n").length - 1;
      return /^\s*(\/\/|#)/.test(textarea.value.split("\n")[lineIdx] || "") ? "$" : "";
    };
    ribbonHost.appendChild(buildRibbon(() => textarea, onCommentLine));
    enableBoxTab(textarea);
    let kind = "expression";
    const preview = buildPreview(() => kind, () => variablesOfText(textarea.value));
    previewHost.appendChild(preview.el);
    const refresh = () => {
      const lineIdx = textarea.value.slice(0, textarea.selectionStart).split("\n").length - 1;
      const found = formulaOfLine(textarea.value.split("\n")[lineIdx] || "");
      if (!found) { preview.update(""); return; }
      kind = found.kind;
      preview.update(found.text);
    };
    ["input", "keyup", "click", "focus"].forEach((ev) => textarea.addEventListener(ev, refresh));
    return { refresh };
  }

  return { attachToPanel, attachToTextarea, renderMath, BOX };
})();
