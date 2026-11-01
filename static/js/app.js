/* Page wiring: tabs, buttons, code generation, running, saving. */
(() => {
  const $ = (id) => document.getElementById(id);
  const AUTOSAVE_KEY = "flowcode.autosave.v1";
  const EXT = { python: "py", java: "java", cpp: "cpp" };

  const state = {
    projectId: null,
    tab: "flowchart",
    algoDirty: false,
    codeLanguage: "python",
    steps: [],
  };

  /* ---------- small helpers ---------- */
  let toastTimer = null;
  function notify(message, isError) {
    const t = $("toast");
    t.textContent = message;
    t.className = "toast" + (isError ? " error" : "");
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { t.hidden = true; }, isError ? 5000 : 2500);
  }

  function setBusy(button, busy, text) {
    if (busy) { button.dataset.label = button.textContent; button.textContent = text; }
    else if (button.dataset.label) { button.textContent = button.dataset.label; }
    button.disabled = busy;
  }

  /* ---------- autosave ---------- */
  let saveTimer = null;
  function scheduleAutosave() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      try {
        localStorage.setItem(AUTOSAVE_KEY, JSON.stringify({
          name: $("project-name").value, language: $("language").value,
          ir: Flowchart.toIR(), algoText: $("algo-text").value, code: $("code").value,
          codeLanguage: state.codeLanguage, projectId: state.projectId,
        }));
      } catch (err) { /* storage may be full or disabled */ }
    }, 400);
  }

  /* ---------- AI connection badge ---------- */
  async function checkAI(showMessage) {
    const badge = $("ai-status");
    badge.className = "ai-badge";
    badge.textContent = "AI: checking...";
    try {
      const st = await api.aiStatus();
      badge.className = "ai-badge " + (st.connected ? "on" : "off");
      badge.textContent = st.connected ? "AI: " + (st.provider === "ollama" ? "Ollama" : "Online") + " ready" : "AI: offline";
      badge.title = st.message + " (click to open AI Settings)";
      if (showMessage) notify(st.message, !st.connected);
      refreshModelPicker();
      return st;
    } catch (err) {
      badge.className = "ai-badge off";
      badge.textContent = "AI: offline";
      badge.title = err.message;
      return { connected: false, message: err.message };
    }
  }

  async function refreshModelPicker() {
    const sel = $("ai-model");
    try {
      const res = await api.aiModels();
      const usable = res.models.filter((m) => m.usable);
      if (res.provider !== "ollama" || !usable.length) { sel.hidden = true; return; }
      sel.innerHTML = "";
      const auto = document.createElement("option");
      auto.value = ""; auto.textContent = "Model: automatic";
      sel.appendChild(auto);
      usable.forEach((m) => {
        const o = document.createElement("option");
        o.value = m.name; o.textContent = m.name;
        sel.appendChild(o);
      });
      if (res.selected && !usable.some((m) => m.name === res.selected)) {
        const o = document.createElement("option");
        o.value = res.selected; o.textContent = res.selected + " (not found)";
        sel.appendChild(o);
      }
      sel.value = res.selected || "";
      sel.hidden = false;
    } catch (err) { sel.hidden = true; }
  }

  /* ---------- problems list ---------- */
  function showProblems(errors, title, ok) {
    const box = $("problems");
    const list = $("problems-list");
    list.innerHTML = "";
    box.classList.toggle("ok", !!ok);
    $("problems-title").textContent = title;
    errors.forEach((e) => {
      const li = document.createElement("li");
      if (e.nodeId) {
        const b = document.createElement("button");
        b.type = "button";
        b.textContent = e.message;
        b.addEventListener("click", () => Flowchart.focusNode(e.nodeId));
        li.appendChild(b);
      } else {
        li.textContent = e.message;
      }
      list.appendChild(li);
    });
    box.hidden = false;
    Flowchart.markErrors(ok ? [] : errors.map((e) => e.nodeId));
  }

  function hideProblems() {
    $("problems").hidden = true;
    Flowchart.clearErrors();
  }

  /* ---------- code / explanation panel ---------- */
  function setCode(code, language, note) {
    $("code").value = code;
    state.codeLanguage = language;
    const n = $("code-note");
    n.textContent = note || "";
    n.hidden = !note;
    scheduleAutosave();
  }

  function renderSteps(steps) {
    state.steps = steps || [];
    const ol = $("steps");
    ol.innerHTML = "";
    state.steps.forEach((s) => {
      const li = document.createElement("li");
      li.style.marginLeft = (s.depth * 18) + "px";
      li.textContent = s.text;
      ol.appendChild(li);
    });
  }

  function setCodeTab(name) {
    document.querySelectorAll("[data-ctab]").forEach((b) => {
      const on = b.dataset.ctab === name;
      b.classList.toggle("active", on);
      b.setAttribute("aria-selected", on);
    });
    $("code").hidden = name !== "code";
    $("steps").hidden = name !== "steps";
    if (name === "steps" && !state.steps.length) {
      $("steps").innerHTML = '<li style="list-style:none;margin-left:-18px" class="muted">Click "Generate Code" to see the steps of your algorithm in plain English.</li>';
    }
  }

  /* ---------- tabs: flowchart <-> algorithm text ---------- */
  const escapeHtml = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  function updateGutter(markedErrors, markedWarnings) {
    const count = $("algo-text").value.split("\n").length;
    const errSet = new Set((markedErrors || []).map((e) => e.line));
    const warnSet = new Set((markedWarnings || []).map((e) => e.line));
    let html = "";
    for (let i = 1; i <= count; i++) {
      html += `<span class="ln${errSet.has(i) ? " err" : warnSet.has(i) ? " warn" : ""}">${i}</span>`;
    }
    const g = $("algo-gutter");
    g.innerHTML = html;
    g.scrollTop = $("algo-text").scrollTop;
  }

  function jumpToLine(line) {
    const ta = $("algo-text");
    const lines = ta.value.split("\n");
    let start = 0;
    for (let i = 0; i < line - 1 && i < lines.length; i++) start += lines[i].length + 1;
    const end = start + (lines[line - 1] || "").length;
    ta.focus();
    ta.setSelectionRange(start, end);
    ta.scrollTop = Math.max(0, (line - 3) * 20);
    $("algo-gutter").scrollTop = ta.scrollTop;
  }

  function problemItem(p) {
    const li = document.createElement("li");
    const top = document.createElement("div");
    top.className = "err-top";
    if (p.line) {
      const b = document.createElement("button");
      b.type = "button"; b.className = "err-line"; b.textContent = "Line " + p.line;
      b.title = "Go to this line";
      b.addEventListener("click", () => jumpToLine(p.line));
      top.appendChild(b);
    }
    const msg = document.createElement("span");
    msg.className = "err-msg";
    msg.textContent = p.message;
    top.appendChild(msg);
    li.appendChild(top);
    if (p.line && p.text != null) {
      const pre = document.createElement("pre");
      pre.className = "err-code";
      const prefix = `${p.line} | `;
      const marker = " ".repeat(prefix.length + (p.col || 0)) + "^".repeat(Math.max(1, Math.min(p.length || 1, 80)));
      pre.innerHTML = `${escapeHtml(prefix + p.text)}\n<span class="caret">${escapeHtml(marker)}</span>`;
      li.appendChild(pre);
    }
    return li;
  }

  function renderSyntax(result) {
    const panel = $("syntax-panel"), head = $("syntax-head"), list = $("algo-errors");
    list.innerHTML = "";
    panel.classList.remove("ok", "bad", "warn");
    if (!$("algo-text").value.trim()) {
      head.textContent = "Syntax check: type your algorithm above.";
      updateGutter();
      return;
    }
    if (!result.ok) {
      const n = result.errors.length;
      panel.classList.add("bad");
      head.textContent = `${n} syntax ${n === 1 ? "error" : "errors"} found. Fix ${n === 1 ? "it" : "them"} to build the flowchart.`;
      result.errors.forEach((e) => list.appendChild(problemItem(e)));
      updateGutter(result.errors, []);
    } else if (result.warnings && result.warnings.length) {
      const n = result.warnings.length;
      panel.classList.add("warn");
      head.textContent = `Syntax is correct, but ${n} ${n === 1 ? "thing needs" : "things need"} fixing before code can be generated.`;
      result.warnings.forEach((e) => list.appendChild(problemItem(e)));
      updateGutter([], result.warnings);
    } else {
      panel.classList.add("ok");
      head.textContent = "No syntax errors found.";
      updateGutter();
    }
  }

  let liveTimer = null;
  function scheduleLiveCheck() {
    clearTimeout(liveTimer);
    liveTimer = setTimeout(async () => {
      if (state.tab !== "algorithm") return;
      try { renderSyntax(await api.parseAlgorithm($("algo-text").value)); }
      catch (err) { $("syntax-head").textContent = err.message; }
    }, 500);
  }

  async function buildFromText() {
    const text = $("algo-text").value;
    $("algo-status").textContent = "";
    let res;
    try { res = await api.parseAlgorithm(text); }
    catch (err) { notify(err.message, true); return false; }
    renderSyntax(res);
    if (!res.ok) return false;
    Flowchart.fromIR(res.ir);
    state.algoDirty = false;
    setTimeout(Flowchart.fit, 30);
    $("algo-status").textContent = "Flowchart built from your text.";
    return true;
  }

  async function showAlgorithmFromFlowchart() {
    const ir = Flowchart.toIR();
    if (!ir.nodes.length) return;
    try {
      const res = await api.toAlgorithm(ir);
      if (res.ok) {
        $("algo-text").value = res.text;
        $("algo-status").textContent = "This text matches your flowchart.";
        renderSyntax({ ok: true, errors: [], warnings: [] });
      } else {
        $("algo-status").textContent = "The flowchart cannot be shown as text yet: " + res.error;
      }
    } catch (err) { notify(err.message, true); }
  }

  async function setTab(name) {
    if (name === state.tab) return;
    const leaving = state.tab;
    document.querySelectorAll("[data-tab]").forEach((b) => {
      const on = b.dataset.tab === name;
      b.classList.toggle("active", on);
      b.setAttribute("aria-selected", on);
    });
    $("view-flowchart").hidden = name !== "flowchart";
    $("view-algorithm").hidden = name !== "algorithm";
    state.tab = name;
    if (name === "algorithm") {
      // Never overwrite text the user has edited but not built yet.
      if (!state.algoDirty) await showAlgorithmFromFlowchart(); else scheduleLiveCheck();
      updateGutter();
    } else if (leaving === "algorithm" && state.algoDirty) {
      const ok = await buildFromText();
      if (!ok) {
        notify("The flowchart was not updated from your text. Go back to Algorithm (Text) to fix it or try again.", true);
      }
    }
  }

  /* ---------- generate / run ---------- */
  async function ensureSynced() {
    if (!state.algoDirty) return true;
    const wasHidden = $("view-flowchart").hidden;
    $("view-flowchart").hidden = false;            // the canvas must be visible while it is drawn
    let ok = false;
    try { ok = await buildFromText(); }
    finally { $("view-flowchart").hidden = wasHidden; }
    if (!ok) {
      notify(state.tab === "algorithm"
        ? "Fix the syntax errors listed under your algorithm first."
        : 'Your algorithm text has errors. Open the "Algorithm (Text)" tab to see them.', true);
      return false;
    }
    return true;
  }
  async function generate() {
    if (!(await ensureSynced())) return;
    const btn = $("btn-generate");
    setBusy(btn, true, "Generating...");
    try {
      const language = $("language").value;
      const res = await api.generate(Flowchart.toIR(), language);
      if (res.ok) {
        setCode(res.code, language, res.note);
        renderSteps(res.steps);
        setCodeTab("code");
        showProblems([{ message: "No problems found. Code generated." }], "Checked", true);
        setTimeout(hideProblems, 2500);
      } else {
        if (res.fallbackCode) {
          setCode(res.fallbackCode, "python", "AI is not available, so the Python version is shown.");
          renderSteps(res.steps);
        }
        showProblems(res.errors || [{ message: "Something went wrong." }], "Problems to fix");
        if (state.tab !== "flowchart") await setTab("flowchart");
      }
    } catch (err) {
      notify(err.message, true);
    } finally {
      setBusy(btn, false);
    }
  }

  /* ---------- console: the program pauses at input() and asks for a value here ---------- */
  let session = null;                       // {id, next, waiting, timer}

  function termAppend(text, className) {
    if (!text) return;
    const holder = $("term-text");
    if (className) {
      const span = document.createElement("span");
      span.className = className;
      span.textContent = text;
      holder.appendChild(span);
    } else {
      holder.appendChild(document.createTextNode(text));
    }
    $("output").scrollTop = $("output").scrollHeight;
  }

  function clearConsole() {
    $("term-text").textContent = "";
    if (!session) hideTermInput();
  }

  function showTermInput() {
    const input = $("term-input");
    input.hidden = false;
    input.value = "";
    input.size = 2;
    input.focus();
    $("output").scrollTop = $("output").scrollHeight;
  }

  function hideTermInput() {
    const input = $("term-input");
    input.hidden = true;
    input.value = "";
  }

  function setRunning(on) {
    const btn = $("btn-run");
    btn.disabled = on;
    btn.textContent = on ? "Running..." : "Run Code";
    $("btn-stop").hidden = !on;
  }

  function finishRun(r) {
    const text = $("term-text").textContent;
    hideTermInput();
    setRunning(false);
    if (r.error) termAppend((text && !text.endsWith("\n") ? "\n" : "") + r.error + "\n", "err");
    if (r.reason) termAppend((text && !text.endsWith("\n") && !r.error ? "\n" : "") + r.reason + "\n", "err");
    else if (r.exitCode === 0) termAppend((text && !text.endsWith("\n") ? "\n" : "") + "[Program finished]\n", "term-note");
    else if (!r.error) termAppend("[Program ended]\n", "term-note");
    session = null;
  }

  async function pollRun() {
    const s = session;
    if (!s) return;
    let r;
    try {
      r = await api.runPoll(s.id, s.next);
    } catch (err) {
      if (session === s) { termAppend("\n" + err.message + "\n", "err"); hideTermInput(); setRunning(false); session = null; }
      return;
    }
    if (session !== s) return;
    if (!r.ok) { termAppend("\n" + (r.error || "The run was lost.") + "\n", "err"); hideTermInput(); setRunning(false); session = null; return; }
    if (r.output) termAppend(r.output);
    s.next = r.next;
    if (r.waiting && !s.waiting) { s.waiting = true; showTermInput(); }
    if (!r.waiting && s.waiting) { s.waiting = false; hideTermInput(); }
    if (r.done) { finishRun(r); return; }
    s.timer = setTimeout(pollRun, r.waiting ? 150 : 60);
  }

  async function submitTermInput() {
    const s = session;
    if (!s || !s.waiting) return;
    const input = $("term-input");
    const value = input.value;
    s.waiting = false;
    hideTermInput();
    termAppend(value + "\n");                 // show what was typed, like a real terminal
    try { await api.runInput(s.id, value); } catch (err) { termAppend(err.message + "\n", "err"); }
  }

  async function stopRun() {
    if (!session) return;
    try { await api.runStop(session.id); } catch (err) { /* the poll will show the result */ }
  }

  async function run() {
    const code = $("code").value;
    if (!code.trim()) { notify('Click "Generate Code" first.', true); return; }
    if (state.codeLanguage !== "python") {
      notify("Running is available for Python code only. Switch the language to Python.", true);
      return;
    }
    if (session) { clearTimeout(session.timer); session = null; }
    $("term-text").textContent = "";
    hideTermInput();
    setRunning(true);
    let res;
    try { res = await api.runStart(code); }
    catch (err) { termAppend(err.message + "\n", "err"); setRunning(false); return; }
    if (!res.ok) { termAppend(res.error + "\n", "err"); setRunning(false); return; }
    session = { id: res.id, next: 0, waiting: false, timer: null };
    pollRun();
  }

  /* ---------- projects ---------- */
  function currentProject() {
    return {
      id: state.projectId, name: $("project-name").value.trim() || "Untitled",
      language: $("language").value, mode: state.tab === "algorithm" ? "algorithm" : "flowchart",
      diagram: Flowchart.toIR(), algorithm_text: $("algo-text").value, code: $("code").value,
    };
  }

  async function save() {
    if (!(await ensureSynced())) return;
    try {
      const res = await api.saveProject(currentProject());
      if (res.ok) { state.projectId = res.id; notify("Saved."); scheduleAutosave(); }
      else notify(res.error || "Could not save.", true);
    } catch (err) { notify(err.message, true); }
  }

  function applyProject(p) {
    state.projectId = p.id || null;
    $("project-name").value = p.name || "Untitled";
    if (p.language) $("language").value = p.language;
    if (state.tab !== "flowchart") {
      $("view-flowchart").hidden = false; $("view-algorithm").hidden = true;
      document.querySelectorAll("[data-tab]").forEach((b) => b.classList.toggle("active", b.dataset.tab === "flowchart"));
      state.tab = "flowchart";
    }
    Flowchart.fromIR(p.diagram);
    state.algoDirty = false;
    $("algo-text").value = p.algorithm_text || "";
    renderSyntax({ ok: true, errors: [], warnings: [] });
    setCode(p.code || "", p.codeLanguage || p.language || "python", "");
    renderSteps([]);
    clearConsole();
    hideProblems();
    setTimeout(Flowchart.fit, 30);
  }

  function openModal(title, build, wide) {
    $("modal-title").textContent = title;
    $("modal").querySelector(".modal-box").classList.toggle("wide", !!wide);
    const body = $("modal-body");
    body.innerHTML = "";
    build(body);
    $("modal").hidden = false;
  }
  const closeModal = () => { $("modal").hidden = true; };

  /* ---------- AI settings: choose provider, manage Ollama models ---------- */
  const SUGGESTED_MODELS = ["qwen2.5-coder:7b", "qwen2.5-coder:3b", "codellama:7b", "deepseek-coder:6.7b"];
  const fmtGB = (bytes) => (bytes > 1e6 ? (bytes / 1e9).toFixed(1) + " GB" : "cloud");

  async function openAiSettings() {
    let settings;
    try { settings = await api.aiSettings(); }
    catch (err) { notify(err.message, true); return; }

    openModal("AI Settings", (body) => {
      const el = (tag, cls, text) => {
        const e = document.createElement(tag);
        if (cls) e.className = cls;
        if (text != null) e.textContent = text;
        return e;
      };
      const row = (labelText, input) => {
        const r = el("div", "form-row");
        const l = el("label", null, labelText);
        input.id = input.id || "ai-" + Math.random().toString(36).slice(2, 8);
        l.htmlFor = input.id;
        r.append(l, input);
        return r;
      };
      const textInput = (value, type) => {
        const i = document.createElement("input");
        i.type = type || "text"; i.value = value || ""; i.autocomplete = "off"; i.spellcheck = false;
        return i;
      };

      const stateBox = el("div", "ai-state off", "Checking...");
      body.appendChild(stateBox);

      /* provider switch */
      const seg = el("div", "seg");
      seg.setAttribute("role", "radiogroup");
      seg.setAttribute("aria-label", "AI provider");
      [["ollama", "Local model (Ollama)"], ["openai", "Online API (OpenAI-compatible)"]].forEach(([value, text]) => {
        const label = document.createElement("label");
        const radio = document.createElement("input");
        radio.type = "radio"; radio.name = "ai-provider"; radio.value = value;
        radio.checked = settings.provider === value;
        radio.addEventListener("change", showProvider);
        label.append(radio, document.createTextNode(text));
        seg.appendChild(label);
      });
      body.appendChild(seg);

      /* --- Ollama --- */
      const ollamaBox = el("div");
      const urlInput = textInput(settings.ollama_url);
      ollamaBox.appendChild(row("Ollama address", urlInput));

      const head1 = el("div", "section-head");
      head1.appendChild(el("h3", null, "Models on this computer"));
      const refreshBtn = el("button", "btn btn-small", "Refresh");
      refreshBtn.type = "button";
      head1.appendChild(refreshBtn);
      ollamaBox.appendChild(head1);
      const offlineBox = el("div", "ai-state off offline-box");
      const offlineText = el("span", null, "Ollama is not running. The models below are already on your computer; start Ollama to use them.");
      const startBtn = el("button", "btn btn-small btn-primary", "Start Ollama");
      startBtn.type = "button";
      offlineBox.append(offlineText, startBtn);
      offlineBox.hidden = true;
      ollamaBox.appendChild(offlineBox);
      const modelList = el("ul", "list model-list");
      ollamaBox.appendChild(modelList);
      ollamaBox.appendChild(el("p", "form-hint", "Pick the model used for Java and C++ code. Coding models such as qwen2.5-coder give the best results."));
      ollamaBox.lastChild.style.marginLeft = "0";

      const head2 = el("div", "section-head");
      head2.appendChild(el("h3", null, "Download a model"));
      ollamaBox.appendChild(head2);
      const dlRow = el("div", "download-row");
      const dlInput = textInput("", "text");
      dlInput.placeholder = "e.g. qwen2.5-coder:7b";
      dlInput.setAttribute("aria-label", "Model name to download");
      const dlBtn = el("button", "btn btn-primary", "Download");
      dlBtn.type = "button";
      dlRow.append(dlInput, dlBtn);
      ollamaBox.appendChild(dlRow);
      const chips = el("div", "chips");
      SUGGESTED_MODELS.forEach((name) => {
        const c = el("button", "chip", name);
        c.type = "button";
        c.addEventListener("click", () => { dlInput.value = name; dlInput.focus(); });
        chips.appendChild(c);
      });
      ollamaBox.appendChild(chips);
      const bar = el("div", "progress");
      const barFill = el("div");
      bar.appendChild(barFill);
      bar.hidden = true;
      const barText = el("div", "progress-text");
      ollamaBox.append(bar, barText);
      body.appendChild(ollamaBox);

      /* --- online --- */
      const onlineBox = el("div");
      const baseInput = textInput(settings.openai_base_url);
      const modelInput = textInput(settings.openai_model);
      const keyInput = textInput("", "password");
      keyInput.placeholder = settings.has_api_key ? "A key is saved. Leave empty to keep it." : "Paste your API key";
      onlineBox.append(row("API address", baseInput), row("Model name", modelInput), row("API key", keyInput));
      onlineBox.appendChild(el("p", "form-hint", "The key is stored only on this computer (database/ai_settings.json). When you generate Java or C++, your flowchart is sent to this service."));
      body.appendChild(onlineBox);

      /* --- footer --- */
      const foot = el("div", "modal-foot");
      const testBtn = el("button", "btn", "Test connection");
      const saveBtn = el("button", "btn btn-primary", "Save");
      testBtn.type = saveBtn.type = "button";
      foot.append(testBtn, saveBtn);
      body.appendChild(foot);

      /* --- behaviour --- */
      const provider = () => body.querySelector('input[name="ai-provider"]:checked').value;
      function showProvider() {
        ollamaBox.hidden = provider() !== "ollama";
        onlineBox.hidden = provider() !== "openai";
      }
      showProvider();

      let selectedModel = settings.ollama_model || "";

      async function refreshState() {
        try {
          const st = await api.aiStatus();
          stateBox.className = "ai-state " + (st.connected ? "on" : "off");
          stateBox.textContent = (st.connected ? "Connected. " : "Not connected. ") + st.message;
        } catch (err) {
          stateBox.className = "ai-state off";
          stateBox.textContent = err.message;
        }
      }

      function modelRow(value, labelNode, size, deletable) {
        const li = document.createElement("li");
        const label = el("label", "model-pick");
        const radio = document.createElement("input");
        radio.type = "radio"; radio.name = "ai-model"; radio.value = value;
        radio.checked = selectedModel === value;
        radio.addEventListener("change", () => { selectedModel = value; });
        label.append(radio, labelNode);
        li.appendChild(label);
        if (size) li.appendChild(el("span", "size", size));
        if (deletable) {
          const del = el("button", "btn btn-small", "Delete");
          del.type = "button";
          del.addEventListener("click", async () => {
            if (!confirm(`Delete the model "${value}" from this computer? You can download it again later.`)) return;
            del.disabled = true;
            try {
              const res = await api.deleteModel(value);
              if (!res.ok) notify(res.error || "Could not delete the model.", true);
              if (selectedModel === value) selectedModel = "";
            } catch (err) { notify(err.message, true); }
            await loadModels();
            await refreshState();
          });
          li.appendChild(del);
        }
        return li;
      }

      async function loadModels() {
        modelList.innerHTML = "";
        modelList.appendChild(modelRow("", el("span", null, "Choose automatically (recommended)"), "", false));
        let res;
        try { res = await api.aiModels(); }
        catch (err) { modelList.appendChild(el("li", "muted", err.message)); return; }
        offlineBox.hidden = !!res.running || provider() !== "ollama";
        if (!res.models.length) {
          modelList.appendChild(el("li", "muted", res.running
            ? "No models installed yet. Download one below."
            : "No downloaded models were found on this computer."));
          return;
        }
        res.models.forEach((m) => {
          const wrap = document.createElement("span");
          wrap.append(el("span", null, m.name));
          if (!m.usable) wrap.append(" ", el("span", "tag", m.name.endsWith(":cloud") ? "online model" : "not for code"));
          else if (res.status && res.status.model === m.name && !settings.ollama_model && selectedModel === "") {
            wrap.append(" ", el("span", "tag best", "used now"));
          }
          const li = modelRow(m.name, wrap, fmtGB(m.size), res.running);
          if (!m.usable) li.querySelector("input").disabled = true;
          modelList.appendChild(li);
        });
      }

      startBtn.addEventListener("click", async () => {
        startBtn.disabled = true; startBtn.textContent = "Starting...";
        try {
          const res = await api.startOllama();
          notify(res.ok ? res.message : res.error, !res.ok);
        } catch (err) { notify(err.message, true); }
        startBtn.disabled = false; startBtn.textContent = "Start Ollama";
        await loadModels();
        await refreshState();
        checkAI(false);
      });
      const payload = () => {
        const p = {
          provider: provider(), ollama_url: urlInput.value, ollama_model: selectedModel,
          openai_base_url: baseInput.value, openai_model: modelInput.value,
        };
        if (keyInput.value.trim()) p.openai_api_key = keyInput.value.trim();
        return p;
      };

      async function saveSettings() {
        const res = await api.saveAiSettings(payload());
        if (!res.ok) { notify(res.message || "Could not save.", true); return false; }
        keyInput.value = "";
        settings = res.settings;
        return true;
      }

      refreshBtn.addEventListener("click", async () => {
        if (await saveSettings()) { await loadModels(); await refreshState(); }
      });
      testBtn.addEventListener("click", async () => {
        stateBox.className = "ai-state off"; stateBox.textContent = "Checking...";
        if (await saveSettings()) { await loadModels(); await refreshState(); await checkAI(false); }
      });
      saveBtn.addEventListener("click", async () => {
        if (await saveSettings()) { closeModal(); await checkAI(false); notify("AI settings saved."); }
      });

      dlBtn.addEventListener("click", async () => {
        const name = dlInput.value.trim();
        if (!name) { dlInput.focus(); return; }
        dlBtn.disabled = true; refreshBtn.disabled = true;
        bar.hidden = false; barFill.style.width = "0";
        barText.textContent = "Starting download...";
        try {
          if (!(await saveSettings())) return;
          await api.pullModel(name, (p) => {
            if (p.total) {
              const pct = Math.round((100 * (p.completed || 0)) / p.total);
              barFill.style.width = pct + "%";
              barText.textContent = `Downloading ${pct}%  (${fmtGB(p.completed || 0)} of ${fmtGB(p.total)})`;
            } else {
              barText.textContent = p.status || "Working...";
            }
          });
          barFill.style.width = "100%";
          barText.textContent = "Download finished.";
          selectedModel = name;
          dlInput.value = "";
          await loadModels();
          await refreshState();
        } catch (err) {
          barText.textContent = "Download failed: " + err.message;
        } finally {
          dlBtn.disabled = false; refreshBtn.disabled = false;
        }
      });

      loadModels().then(refreshState);
    }, true);
  }
  function listRow(label, buttons) {
    const li = document.createElement("li");
    const span = document.createElement("span");
    span.className = "grow";
    span.textContent = label;
    li.appendChild(span);
    buttons.forEach(([text, fn]) => {
      const b = document.createElement("button");
      b.type = "button"; b.className = "btn btn-small"; b.textContent = text;
      b.addEventListener("click", fn);
      li.appendChild(b);
    });
    return li;
  }

  async function openLoad() {
    let projects = [], examples = [];
    try { [projects, examples] = await Promise.all([api.projects(), api.examples()]); }
    catch (err) { notify(err.message, true); return; }
    openModal("Load", (body) => {
      const h1 = document.createElement("h3"); h1.textContent = "Your saved projects"; body.appendChild(h1);
      const ul1 = document.createElement("ul"); ul1.className = "list";
      if (!projects.length) {
        const li = document.createElement("li"); li.className = "muted"; li.textContent = "Nothing saved yet."; ul1.appendChild(li);
      }
      projects.forEach((p) => {
        ul1.appendChild(listRow(`${p.name}  (${p.updated_at.replace("T", " ").replace("+00:00", " UTC")})`, [
          ["Open", async () => {
            try {
              const res = await api.getProject(p.id);
              if (res.ok) { applyProject(res.project); closeModal(); }
            } catch (err) { notify(err.message, true); }
          }],
          ["Delete", async () => {
            if (!confirm(`Delete "${p.name}"?`)) return;
            await api.deleteProject(p.id);
            if (state.projectId === p.id) state.projectId = null;
            openLoad();
          }],
        ]));
      });
      body.appendChild(ul1);

      const h2 = document.createElement("h3"); h2.textContent = "Examples"; body.appendChild(h2);
      const ul2 = document.createElement("ul"); ul2.className = "list";
      examples.forEach((ex) => {
        ul2.appendChild(listRow(ex.name, [["Open", () => {
          applyProject({ name: ex.name, diagram: ex.ir, algorithm_text: ex.text, language: "python" });
          closeModal();
        }]]));
      });
      body.appendChild(ul2);

      const h3 = document.createElement("h3"); h3.textContent = "From a file"; body.appendChild(h3);
      const pick = document.createElement("button");
      pick.type = "button"; pick.className = "btn"; pick.textContent = "Open flowchart file (.json)...";
      pick.addEventListener("click", () => $("file-input").click());
      body.appendChild(pick);
    });
  }

  function download(filename, text, mime) {
    const url = URL.createObjectURL(new Blob([text], { type: mime }));
    const a = document.createElement("a");
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
  }

  function exportAs(kind) {
    const name = ($("project-name").value.trim() || "flowchart").replace(/[^\w\- ]+/g, "").replace(/\s+/g, "_") || "flowchart";
    if (kind === "code") {
      const code = $("code").value;
      if (!code.trim()) { notify('Click "Generate Code" first.', true); return; }
      download(`${name}.${EXT[state.codeLanguage] || "txt"}`, code, "text/plain");
    } else {
      download(`${name}.json`, JSON.stringify(Flowchart.toIR(), null, 2), "application/json");
    }
  }

  function newProject() {
    if (!Flowchart.isEmpty() && !confirm("Start a new flowchart? Unsaved changes will be lost.")) return;
    state.projectId = null;
    $("project-name").value = "Untitled";
    $("algo-text").value = "";
    renderSyntax({ ok: true, errors: [], warnings: [] });
    state.algoDirty = false;
    if (state.tab !== "flowchart") {
      $("view-flowchart").hidden = false; $("view-algorithm").hidden = true;
      document.querySelectorAll("[data-tab]").forEach((b) => b.classList.toggle("active", b.dataset.tab === "flowchart"));
      state.tab = "flowchart";
    }
    Flowchart.newDiagram();
    setCode("", "python", "");
    renderSteps([]);
    clearConsole();
    hideProblems();
    setTimeout(Flowchart.fit, 30);
  }

  /* ---------- wiring ---------- */
  function wire() {
    Flowchart.init($("drawflow"), {
      change: scheduleAutosave,
      notify,
      select: (id) => { $("props-title").textContent = Flowchart.renderProps($("props-body"), id); },
      zoom: (z) => { $("zoom-label").textContent = Math.round(z * 100) + "%"; },
    });

    document.querySelectorAll(".palette-item").forEach((item) => {
      item.addEventListener("dragstart", (e) => e.dataTransfer.setData("text/plain", item.dataset.type));
      item.addEventListener("click", () => Flowchart.addBlockAtCenter(item.dataset.type));
    });
    document.querySelectorAll("[data-tab]").forEach((b) => b.addEventListener("click", () => setTab(b.dataset.tab)));
    document.querySelectorAll("[data-ctab]").forEach((b) => b.addEventListener("click", () => setCodeTab(b.dataset.ctab)));

    $("btn-generate").addEventListener("click", generate);
    $("btn-run").addEventListener("click", run);
    $("btn-new").addEventListener("click", newProject);
    $("btn-save").addEventListener("click", save);
    $("btn-load").addEventListener("click", openLoad);
    $("modal-close").addEventListener("click", closeModal);
    $("modal").addEventListener("click", (e) => { if (e.target === $("modal")) closeModal(); });
    $("btn-build").addEventListener("click", async () => {
      const prev = $("view-flowchart").hidden;
      $("view-flowchart").hidden = false;       // the canvas must be visible while it is drawn
      try { await buildFromText(); }
      finally { $("view-flowchart").hidden = prev; }
    });
    $("algo-text").addEventListener("input", () => {
      state.algoDirty = true;
      $("algo-status").textContent = "";
      updateGutter();
      scheduleLiveCheck();
    });
    $("algo-text").addEventListener("scroll", () => { $("algo-gutter").scrollTop = $("algo-text").scrollTop; });
    $("btn-problems-close").addEventListener("click", hideProblems);
    $("btn-clear").addEventListener("click", clearConsole);
    $("btn-stop").addEventListener("click", stopRun);
    $("term-input").addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); submitTermInput(); }
    });
    $("term-input").addEventListener("input", (e) => { e.target.size = Math.max(2, e.target.value.length + 1); });
    $("output").addEventListener("mousedown", (e) => {          // clicking the console focuses the input
      const input = $("term-input");
      if (!input.hidden && e.target !== input && !window.getSelection().toString()) setTimeout(() => input.focus(), 0);
    });
    $("btn-copy").addEventListener("click", async () => {
      try { await navigator.clipboard.writeText($("code").value); notify("Code copied."); }
      catch (err) { $("code").select(); notify("Press Ctrl+C to copy.", false); }
    });
    $("code").addEventListener("input", scheduleAutosave);
    $("project-name").addEventListener("input", scheduleAutosave);
    $("language").addEventListener("change", async () => {
      scheduleAutosave();
      if ($("language").value !== "python") {
        const st = await checkAI(false);
        if (!st.connected) notify("Java and C++ code needs an AI model. " + st.message, true);
      }
    });
    $("ai-status").addEventListener("click", openAiSettings);
    $("ai-model").addEventListener("change", async () => {
      try {
        const res = await api.saveAiSettings({ ollama_model: $("ai-model").value });
        notify(res.ok ? ($("ai-model").value ? "Model set to " + $("ai-model").value : "Model is chosen automatically.") : res.message, !res.ok);
      } catch (err) { notify(err.message, true); }
      checkAI(false);
    });
    $("btn-ai-settings").addEventListener("click", openAiSettings);

    Formula.attachToTextarea($("algo-text"), $("algo-ribbon"), $("algo-preview"));

    $("btn-undo").addEventListener("click", Flowchart.undo);
    $("btn-redo").addEventListener("click", Flowchart.redo);
    $("btn-delete").addEventListener("click", Flowchart.deleteSelected);
    $("btn-zoom-in").addEventListener("click", Flowchart.zoomIn);
    $("btn-zoom-out").addEventListener("click", Flowchart.zoomOut);
    $("btn-fit").addEventListener("click", Flowchart.fit);

    const menu = $("export-menu");
    $("btn-export").addEventListener("click", (e) => {
      e.stopPropagation();
      menu.hidden = !menu.hidden;
      $("btn-export").setAttribute("aria-expanded", String(!menu.hidden));
    });
    document.addEventListener("click", () => { menu.hidden = true; });
    menu.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => exportAs(b.dataset.export)));

    $("file-input").addEventListener("change", async (e) => {
      const file = e.target.files[0];
      e.target.value = "";
      if (!file) return;
      try {
        const ir = JSON.parse(await file.text());
        if (!Array.isArray(ir.nodes) || !Array.isArray(ir.edges)) throw new Error("bad");
        applyProject({ name: file.name.replace(/\.json$/i, ""), diagram: ir, language: "python" });
        closeModal();
      } catch (err) { notify("That file is not a valid flowchart.", true); }
    });

    document.addEventListener("keydown", (e) => {
      const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") { e.preventDefault(); save(); }
      else if (!typing && (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") { e.preventDefault(); e.shiftKey ? Flowchart.redo() : Flowchart.undo(); }
      else if (!typing && (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "y") { e.preventDefault(); Flowchart.redo(); }
      else if (e.key === "Escape") closeModal();
    });
  }

  async function start() {
    wire();
    const params = new URLSearchParams(location.search);
    let loaded = false;
    if (!params.has("example")) {
      try {
        const saved = JSON.parse(localStorage.getItem(AUTOSAVE_KEY) || "null");
        if (saved && saved.ir && saved.ir.nodes && saved.ir.nodes.length) {
          applyProject({ id: saved.projectId, name: saved.name, language: saved.language, diagram: saved.ir,
                         algorithm_text: saved.algoText, code: saved.code, codeLanguage: saved.codeLanguage });
          loaded = true;
        }
      } catch (err) { /* ignore broken autosave */ }
    }
    if (!loaded) {
      try {
        const examples = await api.examples();
        const ex = examples[parseInt(params.get("example") || "0", 10)] || examples[0];
        applyProject({ name: ex.name, diagram: ex.ir, algorithm_text: ex.text, language: "python" });
      } catch (err) { Flowchart.newDiagram(); notify(err.message, true); }
    }
    setCodeTab("code");
    checkAI(false);
    if (params.get("generate") === "1") generate();
  }

  document.addEventListener("DOMContentLoaded", start);
})();
