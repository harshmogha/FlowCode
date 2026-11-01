/* Flowchart editor (custom canvas).
 *
 * - Every block has four connection dots (top, right, bottom, left).
 * - Drag from any dot to any dot (or drop on a block) to draw an arrow, in any direction.
 * - Click an arrow to select it; press Delete or use the red X to remove it.
 * - Decision / loop arrows carry a label (Yes/No, Body/Exit) that can be flipped.
 */
const Flowchart = (() => {
  const SPECS = {
    start:    { label: "Start",      defaults: { note: "" } },
    end:      { label: "End",        defaults: { note: "" } },
    input:    { label: "Input",      defaults: { variable: "n", varType: "int", prompt: "Enter a number", note: "" } },
    output:   { label: "Output",     defaults: { value: '"Hello"', note: "" } },
    process:  { label: "Process",    defaults: { variable: "x", expression: "0", note: "" } },
    decision: { label: "Decision",   defaults: { condition: "x > 0", note: "" } },
    while:    { label: "While loop", defaults: { condition: "x > 0", note: "" } },
    for:      { label: "For loop",   defaults: { variable: "i", from: "1", to: "10", step: "", note: "" } },
  };
  const SIZE = {            // [width, height] of each block
    start: [130, 40], end: [130, 40], input: [176, 52], output: [176, 52], process: [176, 52],
    decision: [200, 96], while: [200, 84], for: [200, 84],
  };
  const SLOT = 200;         // layout slot width used by the server-side auto layout
  const DIRS = { top: [0, -1], bottom: [0, 1], left: [-1, 0], right: [1, 0] };
  const SIDES = ["top", "right", "bottom", "left"];
  const HANDLE_SETS = { decision: ["true", "false"], while: ["body", "exit"], for: ["body", "exit"] };
  const HANDLE_TEXT = { true: "Yes", false: "No", body: "Body", exit: "Exit" };
  const HANDLE_HELP = { true: "Yes (condition is true)", false: "No (condition is false)", body: "Body (repeat these steps)", exit: "Exit (leave the loop)" };
  const FIELDS = {
    input: [
      { key: "variable", label: "Variable name", hint: "Where the typed value is stored, e.g. n. To read several values on one line write names with commas (a, b, c), or choose a List type to read any number of values" },
      { key: "prompt", label: "Message", hint: "Shown to the user, e.g. Enter a number" },
      { key: "varType", label: "Type", type: "select", options: [
        ["int", "Whole number"], ["float", "Decimal number"], ["text", "Text"],
        ["list_int", "List of whole numbers (any count)"], ["list_float", "List of decimal numbers (any count)"]] },
    ],
    output: [{ key: "value", label: "Show", math: "list", hint: 'Text goes in quotes: "Even". Several values: "Sum is", total' }],
    process: [
      { key: "variable", label: "Set variable", hint: "e.g. total   or   a[i]" },
      { key: "expression", label: "To value", math: "expression", hint: "e.g. total + i      (mod = remainder, div = whole division)" },
    ],
    decision: [{ key: "condition", label: "Condition", math: "condition", hint: "e.g. n mod 2 = 0     (mod = remainder, = means equals)" }],
    while: [{ key: "condition", label: "Repeat while", math: "condition", hint: "e.g. k > 1" }],
    for: [
      { key: "variable", label: "Counter", hint: "e.g. i" },
      { key: "from", label: "From", math: "expression", hint: "First value, e.g. 1" },
      { key: "to", label: "To (included)", math: "expression", hint: "Last value, e.g. n" },
      { key: "step", label: "Step (optional)", math: "expression", hint: "Leave empty for 1. Use -1 to count down." },
    ],
  };
  // Every block can have a note. It becomes a comment in the code. Formulas go between $ signs.
  const NOTE_FIELD = {
    key: "note", label: "Note", type: "note", math: "note",
    hint: "Optional. Written as a comment above this block's code. Put formulas between $ signs, e.g. Roots: $x = (-b + sqrt(b^2 - 4*a*c)) / (2*a)$",
  };
  Object.keys(SPECS).forEach((t) => { FIELDS[t] = (FIELDS[t] || []).concat([NOTE_FIELD]); });
  const SVG_DECISION = '<svg viewBox="0 0 200 96" preserveAspectRatio="none"><polygon points="100,2 198,48 100,94 2,48"/></svg>';
  const SVG_LOOP = '<svg viewBox="0 0 200 84" preserveAspectRatio="none"><polygon points="24,2 176,2 198,42 176,82 24,82 2,42"/></svg>';
  const SVG_NS = "http://www.w3.org/2000/svg";
  const STUB = 24;

  let container = null, world = null, svg = null, ui = null, delBtn = null;
  const nodes = new Map();
  const edges = new Map();
  let nextNodeId = 1, nextEdgeId = 1;
  let view = { x: 0, y: 0, z: 1 };
  let sel = null;                 // {kind: "node"|"edge", id}
  let drag = null;
  let restoring = false, commitTimer = null;
  let history = { stack: [], index: -1 };
  const hooks = { change: () => {}, select: () => {}, zoom: () => {}, notify: () => {} };

  const esc = (s) => String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const svgEl = (tag, attrs) => {
    const e = document.createElementNS(SVG_NS, tag);
    Object.entries(attrs || {}).forEach(([k, v]) => e.setAttribute(k, v));
    return e;
  };

  /* ================= block appearance ================= */
  function nodeHtml(type, d) {
    const t = (s) => `<span class="t">${esc(s)}</span>`;
    switch (type) {
      case "start": return '<div class="shape shape-start">Start</div>';
      case "end": return '<div class="shape shape-end">End</div>';
      case "input":
        return `<div class="shape shape-io shape-input"><div class="inner"><b>Input</b>${t(d.prompt ? d.prompt + " (" + d.variable + ")" : "Read " + d.variable)}</div></div>`;
      case "output":
        return `<div class="shape shape-io shape-output"><div class="inner"><b>Output</b>${t(d.value)}</div></div>`;
      case "process":
        return `<div class="shape shape-process">${t((d.variable || "") + " = " + (d.expression || ""))}</div>`;
      case "decision":
        return `<div class="shape shape-svg shape-decision">${SVG_DECISION}<div class="text">${t((d.condition || "") + " ?")}</div></div>`;
      case "while":
        return `<div class="shape shape-svg shape-loop">${SVG_LOOP}<div class="text"><b>While</b>${t(d.condition)}</div></div>`;
      case "for":
        return `<div class="shape shape-svg shape-loop">${SVG_LOOP}<div class="text"><b>For</b>${t(d.variable + " = " + d.from + " to " + d.to + (d.step ? " step " + d.step : ""))}</div></div>`;
      default: return "";
    }
  }

  const blockName = (n) => {
    const d = n.data;
    switch (n.type) {
      case "start": case "end": return SPECS[n.type].label;
      case "input": return "Input " + d.variable;
      case "output": return "Output " + d.value;
      case "process": return d.variable + " = " + d.expression;
      case "decision": return "Decision: " + d.condition;
      case "while": return "While " + d.condition;
      default: return "For " + d.variable;
    }
  };

  /* ================= geometry ================= */
  const nodeLeft = (n) => n.x + (SLOT - SIZE[n.type][0]) / 2;
  const nodeBox = (n) => {
    const [w, h] = SIZE[n.type], l = nodeLeft(n);
    return { l, t: n.y, r: l + w, b: n.y + h };
  };
  /* the block plus its note card (arrows keep clear of both) */
  const obstacleBox = (n) => {
    const b = nodeBox(n);
    if (noteIsOpen(n)) b.r += NOTE_GAP + NOTE_WIDTH;
    return b;
  };
  function portPoint(n, side) {
    const b = nodeBox(n), cx = (b.l + b.r) / 2, cy = (b.t + b.b) / 2;
    return side === "top" ? [cx, b.t] : side === "bottom" ? [cx, b.b] : side === "left" ? [b.l, cy] : [b.r, cy];
  }

  function autoSide(dst, from) {            // side of `dst` that faces the point `from`
    const b = nodeBox(dst), cx = (b.l + b.r) / 2, cy = (b.t + b.b) / 2;
    const dx = from[0] - cx, dy = from[1] - cy;
    if (Math.abs(dx) / ((b.r - b.l) / 2) > Math.abs(dy) / ((b.b - b.t) / 2)) return dx < 0 ? "left" : "right";
    return dy < 0 ? "top" : "bottom";
  }

  /* Right-angled route between two ports. Returns a list of points. */
  function route(P, sS, Q, sT) {
    const [dsx, dsy] = DIRS[sS], [dtx, dty] = DIRS[sT];
    const A = [P[0] + dsx * STUB, P[1] + dsy * STUB];
    const B = [Q[0] + dtx * STUB, Q[1] + dty * STUB];
    const boxes = Array.from(nodes.values()).map(obstacleBox);
    const bandBoxes = (lo, hi, axis) => boxes.filter((b) => axis === "y"
      ? b.b > lo - 10 && b.t < hi + 10
      : b.r > lo - 10 && b.l < hi + 10);
    const sv = dsx === 0, tv = dtx === 0;
    let pts;

    if (sv && tv) {
      const forward = (sS === "bottom" && sT === "top" && B[1] >= P[1] + 4) ||
                      (sS === "top" && sT === "bottom" && B[1] <= P[1] - 4);
      if (forward) {
        pts = [P, [P[0], B[1]], [Q[0], B[1]], Q];
      } else {                                   // go around: sideways lane left or right of everything in between
        const bb = bandBoxes(Math.min(A[1], B[1]), Math.max(A[1], B[1]), "y");
        const right = Math.max(P[0], Q[0], ...bb.map((b) => b.r)) + 34;
        const left = Math.min(P[0], Q[0], ...bb.map((b) => b.l)) - 34;
        const lane = Math.abs(P[0] - right) + Math.abs(Q[0] - right) <= Math.abs(P[0] - left) + Math.abs(Q[0] - left) ? right : left;
        pts = [P, A, [lane, A[1]], [lane, B[1]], B, Q];
      }
    } else if (!sv && !tv) {
      const forward = (sS === "right" && sT === "left" && B[0] >= P[0] + 4) ||
                      (sS === "left" && sT === "right" && B[0] <= P[0] - 4);
      if (forward) {
        pts = [P, [B[0], P[1]], [B[0], Q[1]], Q];
      } else {
        const bb = bandBoxes(Math.min(A[0], B[0]), Math.max(A[0], B[0]), "x");
        const bottom = Math.max(P[1], Q[1], ...bb.map((b) => b.b)) + 34;
        const top = Math.min(P[1], Q[1], ...bb.map((b) => b.t)) - 34;
        const lane = Math.abs(P[1] - bottom) + Math.abs(Q[1] - bottom) <= Math.abs(P[1] - top) + Math.abs(Q[1] - top) ? bottom : top;
        pts = [P, A, [A[0], lane], [B[0], lane], B, Q];
      }
    } else if (sv) {                              // leave vertically, enter horizontally
      const C = [P[0], Q[1]];
      if ((C[1] - P[1]) * dsy >= 10 && (Q[0] - C[0]) * -dtx >= 10) {
        pts = [P, C, Q];
      } else {
        const bb = bandBoxes(Math.min(A[1], B[1]), Math.max(A[1], B[1]), "y");
        const lane = sT === "right"
          ? Math.max(B[0], ...bb.map((b) => b.r)) + 34
          : Math.min(B[0], ...bb.map((b) => b.l)) - 34;
        pts = [P, A, [lane, A[1]], [lane, B[1]], B, Q];
      }
    } else {                                      // leave horizontally, enter vertically
      const C = [Q[0], P[1]];
      if (Math.abs(Q[0] - P[0]) <= 2 && (Q[1] - P[1]) * -dty >= 10) {
        pts = [P, Q];                                  // straight out of the side dot, e.g. from a decision's corner
      } else if ((C[0] - P[0]) * dsx >= 10 && (Q[1] - C[1]) * -dty >= 10) {
        pts = [P, C, Q];
      } else {
        const lo = Math.min(A[1], B[1]), hi = Math.max(A[1], B[1]);
        let x = A[0];
        for (let guard = 0, moved = true; moved && guard < 20; guard++) {
          moved = false;
          for (const b of boxes) {
            if (b.t < hi && b.b > lo && x > b.l - 12 && x < b.r + 12 && !(P[0] >= b.l - 2 && P[0] <= b.r + 2 && P[1] >= b.t - 2 && P[1] <= b.b + 2)) {
              x = dsx > 0 ? b.r + 28 : b.l - 28;
              moved = true;
            }
          }
        }
        pts = [P, [x, P[1]], [x, B[1]], B, Q];
      }
    }
    return pts.filter((p, i) => i === 0 || p[0] !== pts[i - 1][0] || p[1] !== pts[i - 1][1]);
  }

  /* ================= edges ================= */
  const edgesFrom = (nid) => Array.from(edges.values()).filter((e) => e.source === nid);
  const edgesOf = (nid) => Array.from(edges.values()).filter((e) => e.source === nid || e.target === nid);

  function polylineMid(pts) {
    let total = 0;
    for (let i = 1; i < pts.length; i++) total += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
    let run = total / 2;
    for (let i = 1; i < pts.length; i++) {
      const seg = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
      if (run <= seg && seg > 0) {
        const k = run / seg;
        return [pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * k, pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * k];
      }
      run -= seg;
    }
    return pts[0];
  }

  function placeAt(el, p) {
    el.style.left = p[0] + "px";
    el.style.top = p[1] + "px";
  }

  function renderEdge(edge) {
    const s = nodes.get(edge.source), t = nodes.get(edge.target);
    if (!s || !t) return;
    const P = portPoint(s, edge.sS), Q = portPoint(t, edge.tS);
    const pts = route(P, edge.sS, Q, edge.tS);
    const [dx, dy] = DIRS[edge.tS];
    pts[pts.length - 1] = [Q[0] + dx * 8, Q[1] + dy * 8];             // stop just outside the dot
    const tip = pts[pts.length - 1];
    const base = [tip[0] + dx * 10, tip[1] + dy * 10], perp = [-dy, dx];
    const line = "M " + pts.map((p) => p[0] + " " + p[1]).join(" L ");
    edge.hit.setAttribute("d", line);
    edge.line.setAttribute("d", line +
      ` M ${base[0] + perp[0] * 5} ${base[1] + perp[1] * 5} L ${tip[0]} ${tip[1]} L ${base[0] - perp[0] * 5} ${base[1] - perp[1] * 5}`);
    edge.pts = pts;
    if (edge.label) {
      const ls = DIRS[edge.sS];
      placeAt(edge.label, [P[0] + ls[0] * 26 + (ls[0] === 0 ? 20 : 0), P[1] + ls[1] * 26 + (ls[1] === 0 ? -14 : 0)]);
    }
    if (sel && sel.kind === "edge" && sel.id === edge.id) placeAt(delBtn, polylineMid(pts));
  }

  function syncLabel(edge) {
    const wants = !!HANDLE_SETS[nodes.get(edge.source).type];
    if (wants && !edge.label) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "fc-label";
      b.title = "Click to switch between the two meanings";
      b.addEventListener("mousedown", (e) => e.stopPropagation());
      b.addEventListener("click", (e) => { e.stopPropagation(); flipHandle(edge); });
      ui.appendChild(b);
      edge.label = b;
    }
    if (edge.label) {
      edge.label.textContent = HANDLE_TEXT[edge.handle] || "";
      edge.label.dataset.handle = edge.handle;
      if (!wants) { edge.label.remove(); edge.label = null; }
    }
  }

  function addEdge(spec) {
    const s = nodes.get(spec.source), t = nodes.get(spec.target);
    if (!s || !t) return null;
    const id = String(nextEdgeId++);
    const g = svgEl("g", { class: "fc-edge" });
    const hit = svgEl("path", { class: "fc-edge-hit" });
    const line = svgEl("path", { class: "fc-edge-line" });
    g.append(hit, line);
    svg.appendChild(g);
    const edge = { id, source: spec.source, target: spec.target, handle: spec.handle || "next",
                   sS: spec.sS, tS: spec.tS, g, hit, line, label: null, pts: [] };
    hit.addEventListener("mousedown", (e) => { e.stopPropagation(); e.preventDefault(); selectEdge(id); container.focus(); });
    edges.set(id, edge);
    syncLabel(edge);
    renderEdge(edge);
    return edge;
  }

  function removeEdge(edge) {
    if (sel && sel.kind === "edge" && sel.id === edge.id) clearSelection();
    edge.g.remove();
    if (edge.label) edge.label.remove();
    edges.delete(edge.id);
  }

  function flipHandle(edge) {
    const set = HANDLE_SETS[nodes.get(edge.source).type];
    if (!set) return;
    setHandle(edge, set[0] === edge.handle ? set[1] : set[0]);
  }

  function setHandle(edge, handle) {
    const other = edgesFrom(edge.source).find((e) => e !== edge && e.handle === handle);
    if (other) { other.handle = edge.handle; syncLabel(other); renderEdge(other); }
    edge.handle = handle;
    syncLabel(edge);
    renderEdge(edge);
    scheduleCommit();
    if (sel && sel.kind === "edge" && sel.id === edge.id) hooks.select("edge:" + edge.id);
  }

  function tryConnect(src, sS, dst, tS) {
    if (src.id === dst.id) { hooks.notify("A block cannot connect to itself.", true); return null; }
    if (src.type === "end") { hooks.notify("The End block has no outgoing arrow.", true); return null; }
    if (dst.type === "start") { hooks.notify("Nothing can lead into the Start block.", true); return null; }
    const out = edgesFrom(src.id);
    if (out.some((e) => e.target === dst.id)) { hooks.notify("Those two blocks are already connected.", true); return null; }
    let handle = "next";
    const set = HANDLE_SETS[src.type];
    if (set) {
      const free = set.filter((h) => !out.some((e) => e.handle === h));
      if (!free.length) {
        hooks.notify(`This block already has two arrows (${HANDLE_TEXT[set[0]]} and ${HANDLE_TEXT[set[1]]}). Delete one first.`, true);
        return null;
      }
      const preferred = src.type === "decision"
        ? (sS === "left" ? "true" : sS === "right" ? "false" : free[0])
        : (sS === "bottom" || sS === "top" ? "body" : "exit");
      handle = free.includes(preferred) ? preferred : free[0];
    } else {
      out.forEach(removeEdge);                      // a normal block has one arrow: the new one replaces it
    }
    const edge = addEdge({ source: src.id, target: dst.id, handle, sS, tS });
    scheduleCommit();
    return edge;
  }

  /* ================= selection ================= */
  function clearSelection(silent) {
    if (sel && sel.kind === "node" && nodes.get(sel.id)) nodes.get(sel.id).el.classList.remove("selected");
    if (sel && sel.kind === "edge" && edges.get(sel.id)) edges.get(sel.id).g.classList.remove("selected");
    delBtn.hidden = true;
    const had = !!sel;
    sel = null;
    if (had && !silent) hooks.select(null);
  }

  function selectNode(id) {
    if (sel && sel.kind === "node" && sel.id === id) return;
    clearSelection(true);
    sel = { kind: "node", id };
    nodes.get(id).el.classList.add("selected");
    hooks.select(id);
  }

  function selectEdge(id) {
    if (sel && sel.kind === "edge" && sel.id === id) return;
    clearSelection(true);
    sel = { kind: "edge", id };
    const edge = edges.get(id);
    edge.g.classList.add("selected");
    edge.g.parentNode.appendChild(edge.g);           // draw on top
    delBtn.hidden = false;
    placeAt(delBtn, polylineMid(edge.pts));
    hooks.select("edge:" + id);
  }

  /* ================= nodes ================= */
  function positionNode(n) {
    const [w, h] = SIZE[n.type];
    n.el.style.left = nodeLeft(n) + "px";
    n.el.style.top = n.y + "px";
    n.el.style.width = w + "px";
    n.el.style.height = h + "px";
  }

  function createNode(type, x, y, data) {
    const id = String(nextNodeId++);
    const n = { id, type, x, y, data: Object.assign({}, SPECS[type].defaults, data || {}), el: null };
    const el = document.createElement("div");
    el.className = "fc-node node-" + type;
    el.dataset.id = id;
    el.innerHTML = `<div class="fc-content">${nodeHtml(type, n.data)}</div>` +
      '<button type="button" class="fc-note-badge" hidden aria-expanded="false" aria-label="Open note">i</button>' +
      SIDES.map((s) => `<span class="fc-port port-${s}" data-side="${s}"></span>`).join("");
    n.el = el;
    el.querySelector(".fc-note-badge").addEventListener("click", (e) => { e.stopPropagation(); setNoteOpen(n, !n.noteOpen); });
    world.appendChild(el);
    nodes.set(id, n);
    positionNode(n);
    renderNoteCard(n);
    return n;
  }

  /* ---- notes: a yellow "i" button on the block opens the note; the x closes it ---- */
  const NOTE_GAP = 46, NOTE_WIDTH = 210;
  const noteCache = new Map();
  const noteText = (n) => String(n.data.note || "").trim();
  const noteIsOpen = (n) => !!(n.noteOpen && noteText(n));

  function paintNote(n, card, segments) {
    card.innerHTML =
      '<div class="fc-note-head"><span class="fc-note-title">Note</span><span class="fc-note-tools">' +
      '<button type="button" class="fc-note-act fc-note-edit" title="Edit this note">Edit</button>' +
      '<button type="button" class="fc-note-act fc-note-del" title="Delete this note">Delete</button>' +
      '<button type="button" class="fc-note-close" aria-label="Close note" title="Close note">\u00d7</button></span></div>' +
      '<div class="fc-note-body"></div>';
    card.querySelector(".fc-note-close").addEventListener("click", (e) => { e.stopPropagation(); setNoteOpen(n, false); });
    card.querySelector(".fc-note-edit").addEventListener("click", (e) => { e.stopPropagation(); editNote(n); });
    card.querySelector(".fc-note-del").addEventListener("click", (e) => { e.stopPropagation(); deleteNote(n); });
    const body = card.querySelector(".fc-note-body");
    segments.forEach((seg) => {
      const span = document.createElement("span");
      if (seg.text != null) {
        span.className = "fc-note-text";
        span.textContent = seg.text;
      } else if (seg.latex) {
        span.className = "fc-note-math";
        if (typeof Formula !== "undefined") Formula.renderMath(span, seg.latex); else span.textContent = seg.latex;
      } else {
        span.className = "fc-note-bad";
        span.textContent = "$" + (seg.raw || "") + "$";
        span.title = seg.error || "";
      }
      body.appendChild(span);
    });
  }

  function renderNoteCard(n) {
    const text = noteText(n);
    const badge = n.el.querySelector(".fc-note-badge");
    let card = n.el.querySelector(".fc-note-card");
    clearTimeout(n.noteTimer);
    badge.hidden = !text;
    if (!text) n.noteOpen = false;
    badge.setAttribute("aria-expanded", n.noteOpen ? "true" : "false");
    badge.title = n.noteOpen ? "Close note" : "Open note";
    badge.classList.toggle("open", !!n.noteOpen);
    if (!n.noteOpen) { if (card) card.remove(); return; }
    if (!card) {
      card = document.createElement("div");
      card.className = "fc-note-card";
      card.setAttribute("role", "note");
      n.el.appendChild(card);
    }
    if (noteCache.has(text)) { paintNote(n, card, noteCache.get(text)); return; }
    paintNote(n, card, [{ text: text.replace(/\$/g, "") }]);        // plain text right away
    if (!text.includes("$") || typeof api === "undefined") return;
    n.noteTimer = setTimeout(async () => {                           // formulas typeset a moment later
      try {
        const res = await api.formulaPreview(text, "note", []);
        if (res && res.segments) {
          noteCache.set(text, res.segments);
          if (noteText(n) === text && n.noteOpen && card.isConnected) paintNote(n, card, res.segments);
        }
      } catch (err) { /* keep the plain text */ }
    }, 250);
  }

  /* delete a block's note (undo brings it back) */
  function deleteNote(n) {
    if (!noteText(n)) return;
    n.data.note = "";
    n.noteOpen = false;
    refreshNode(n);
    edges.forEach(renderEdge);
    scheduleCommit();
    if (sel && sel.kind === "node" && sel.id === n.id) hooks.select(n.id);      // refresh the Properties panel
    hooks.notify("Note deleted. Press Ctrl+Z (or the undo button) to bring it back.");
  }

  /* open the block's Note box in the Properties panel */
  function editNote(n) {
    selectNode(n.id);
    const box = document.getElementById("prop-" + n.id + "-note");
    if (box) { box.focus(); box.setSelectionRange(box.value.length, box.value.length); }
  }

  function setNoteOpen(n, open) {
    n.noteOpen = !!open;
    renderNoteCard(n);
    edges.forEach(renderEdge);                    // an open note is an obstacle for arrows
  }

  function addBlock(type, x, y, data) {
    if (!SPECS[type]) return null;
    if (type === "start" && Array.from(nodes.values()).some((n) => n.type === "start")) {
      hooks.notify("There is already a Start block. A flowchart has only one.", true);
      return null;
    }
    const n = createNode(type, Math.round(x), Math.round(y), data);
    selectNode(n.id);
    scheduleCommit();
    return n.id;
  }

  function addBlockAtCenter(type) {
    const r = container.getBoundingClientRect();
    const p = clientToWorld(r.left + r.width / 2, r.top + r.height / 3);
    const k = nodes.size % 5;
    return addBlock(type, p[0] - SLOT / 2 + k * 14, p[1] - 20 + k * 14);
  }

  function removeNode(id) {
    const n = nodes.get(id);
    if (!n) return;
    edgesOf(id).forEach(removeEdge);
    if (sel && sel.kind === "node" && sel.id === id) clearSelection();
    n.el.remove();
    nodes.delete(id);
  }

  function deleteSelected() {
    if (!sel) return;
    if (sel.kind === "node") removeNode(sel.id);
    else if (edges.get(sel.id)) removeEdge(edges.get(sel.id));
    scheduleCommit();
  }

  function refreshNode(n) {
    n.el.querySelector(".fc-content").innerHTML = nodeHtml(n.type, n.data);
    renderNoteCard(n);
  }

  function getData(id) {
    const n = nodes.get(String(id));
    return n ? Object.assign({ type: n.type }, n.data) : null;
  }

  function setField(id, key, value) {
    const n = nodes.get(id);
    if (!n) return;
    n.data[key] = value;
    refreshNode(n);
    clearErrors();
    scheduleCommit();
  }

  /* ================= property panel ================= */
  function renderProps(target, id) {
    target.innerHTML = "";
    if (id && String(id).startsWith("edge:")) return renderEdgeProps(target, edges.get(String(id).slice(5)));
    const n = id ? nodes.get(String(id)) : null;
    if (!n) {
      target.innerHTML = '<p class="muted">Click a block or an arrow on the canvas to edit it.</p>';
      return "Properties";
    }
    const fields = FIELDS[n.type];
    if (!fields) {
      target.innerHTML = `<p class="muted">The ${esc(SPECS[n.type].label)} block has nothing to edit.</p>`;
      return "Block Properties: " + SPECS[n.type].label;
    }
    const mathFields = [];
    fields.forEach((f) => {
      const input = f.type === "select" ? document.createElement("select")
        : f.type === "note" ? document.createElement("textarea") : document.createElement("input");
      if (f.type === "select") {
        f.options.forEach(([v, text]) => {
          const o = document.createElement("option");
          o.value = v; o.textContent = text;
          input.appendChild(o);
        });
      } else if (f.type === "note") {
        input.rows = 3; input.className = "note-input"; input.spellcheck = true;
        input.placeholder = "e.g. Step 1: find the discriminant $D = b^2 - 4*a*c$";
      } else {
        input.type = "text"; input.autocomplete = "off"; input.spellcheck = false;
      }
      input.id = `prop-${n.id}-${f.key}`;
      input.value = n.data[f.key] == null ? "" : n.data[f.key];
      input.addEventListener(f.type === "select" ? "change" : "input", () => setField(n.id, f.key, input.value));
      const parts = addRow(target, f.label, input, f.hint);
      if (f.type === "note") {
        const label = parts.row.firstChild;
        const left = document.createElement("div");
        left.className = "note-left";
        const del = document.createElement("button");
        del.type = "button";
        del.className = "btn btn-small";
        del.textContent = "Delete note";
        del.title = "Remove this block's note";
        del.disabled = !String(input.value).trim();
        input.addEventListener("input", () => { del.disabled = !input.value.trim(); });
        del.addEventListener("click", () => deleteNote(n));
        parts.row.replaceChild(left, label);
        left.append(label, del);
      }
      if (f.math && typeof Formula !== "undefined") {
        mathFields.push({ input, kind: f.math, row: parts.row, anchor: parts.hint || parts.row });
      }
    });
    if (mathFields.length) Formula.attachToPanel(target, mathFields, variableNames);
    return "Block Properties: " + SPECS[n.type].label;
  }

  function addRow(target, labelText, input, hint) {
    const row = document.createElement("div");
    row.className = "prop-row";
    const label = document.createElement("label");
    label.htmlFor = input.id;
    label.textContent = labelText;
    row.append(label, input);
    target.appendChild(row);
    let h = null;
    if (hint) {
      h = document.createElement("div");
      h.className = "prop-hint";
      h.textContent = hint;
      target.appendChild(h);
    }
    return { row, hint: h };
  }

  /* names of variables the flowchart sets (used by the formula preview for "not set" hints) */
  function variableNames() {
    const out = new Set();
    nodes.forEach((n) => {
      if (n.type !== "input" && n.type !== "for" && n.type !== "process") return;
      String(n.data.variable || "").split(",").forEach((part) => {
        const v = part.trim();
        if (/^[A-Za-z_]\w*$/.test(v)) out.add(v);
      });
    });
    return Array.from(out);
  }

  function renderEdgeProps(target, edge) {
    if (!edge) { target.innerHTML = '<p class="muted">Click a block or an arrow on the canvas to edit it.</p>'; return "Properties"; }
    const s = nodes.get(edge.source), t = nodes.get(edge.target);
    const p = document.createElement("p");
    p.className = "edge-summary";
    p.textContent = `From "${blockName(s)}" to "${blockName(t)}"`;
    target.appendChild(p);

    const select = (idSuffix, options, value, onChange) => {
      const el = document.createElement("select");
      el.id = `edge-${edge.id}-${idSuffix}`;
      options.forEach(([v, text]) => {
        const o = document.createElement("option");
        o.value = v; o.textContent = text;
        el.appendChild(o);
      });
      el.value = value;
      el.addEventListener("change", () => onChange(el.value));
      return el;
    };
    const set = HANDLE_SETS[s.type];
    if (set) {
      addRow(target, "Meaning", select("meaning", set.map((h) => [h, HANDLE_HELP[h]]), edge.handle, (v) => setHandle(edge, v)),
        "Which way the flow goes from this block. Clicking the small label on the arrow also switches it.");
    }
    const sideOptions = SIDES.map((x) => [x, x[0].toUpperCase() + x.slice(1)]);
    addRow(target, "Leaves from", select("from", sideOptions, edge.sS, (v) => { edge.sS = v; renderEdge(edge); scheduleCommit(); }), null);
    addRow(target, "Enters at", select("to", sideOptions, edge.tS, (v) => { edge.tS = v; renderEdge(edge); scheduleCommit(); }), null);
    const del = document.createElement("button");
    del.type = "button";
    del.className = "btn btn-small";
    del.textContent = "Delete this arrow";
    del.addEventListener("click", deleteSelected);
    target.appendChild(del);
    return "Arrow Properties";
  }

  /* ================= IR conversion ================= */
  function defaultSides(srcType, handle, dstTargetHandle) {
    let sS = "bottom";
    if (srcType === "decision") sS = handle === "true" ? "left" : "right";
    else if (srcType === "while" || srcType === "for") sS = handle === "exit" ? "left" : "bottom";
    return { sS, tS: dstTargetHandle === "return" ? "right" : "top" };
  }

  function toIR() {
    const irNodes = Array.from(nodes.values()).map((n) =>
      Object.assign({ id: "n" + n.id, type: n.type }, n.data, { pos: { x: n.x, y: n.y } }));
    const irEdges = Array.from(edges.values()).map((e) => ({
      source: "n" + e.source, sourceHandle: e.handle, target: "n" + e.target, targetHandle: "in",
      sourceSide: e.sS, targetSide: e.tS,
    }));
    return { language: "python", nodes: irNodes, edges: irEdges };
  }

  function fromIR(ir, opts) {
    restoring = true;
    clearTimeout(commitTimer);
    try {
      clearSelection();
      Array.from(edges.values()).forEach((e) => { e.g.remove(); if (e.label) e.label.remove(); });
      edges.clear();
      nodes.forEach((n) => n.el.remove());
      nodes.clear();
      const map = {};
      const byId = {};
      (ir.nodes || []).forEach((n) => {
        if (!SPECS[n.type]) return;
        const data = {};
        Object.keys(SPECS[n.type].defaults).forEach((k) => { data[k] = n[k] != null ? n[k] : SPECS[n.type].defaults[k]; });
        const pos = n.pos || { x: 40, y: 40 };
        map[n.id] = createNode(n.type, pos.x, pos.y, data).id;
        byId[n.id] = n;
      });
      (ir.edges || []).forEach((e) => {
        const s = byId[e.source], from = map[e.source], to = map[e.target];
        if (!s || !from || !to) return;
        const handle = e.sourceHandle || "next";
        const d = defaultSides(s.type, handle, e.targetHandle);
        addEdge({ source: from, target: to, handle,
                  sS: SIDES.includes(e.sourceSide) ? e.sourceSide : d.sS,
                  tS: SIDES.includes(e.targetSide) ? e.targetSide : d.tS });
      });
    } finally {
      restoring = false;
    }
    if (!(opts && opts.keepHistory)) {
      history = { stack: [], index: -1 };
      commit();
    }
  }

  function newDiagram() {
    fromIR({
      nodes: [
        { id: "a", type: "start", pos: { x: 260, y: 30 } },
        { id: "b", type: "end", pos: { x: 260, y: 330 } },
      ],
      edges: [],
    });
  }

  const isEmpty = () => nodes.size === 0;

  /* ================= history ================= */
  function scheduleCommit() {
    if (restoring) return;
    clearTimeout(commitTimer);
    commitTimer = setTimeout(commit, 200);
  }

  function commit() {
    if (restoring) return;
    const snap = JSON.stringify(toIR());
    if (history.stack[history.index] === snap) return;
    history.stack = history.stack.slice(0, history.index + 1);
    history.stack.push(snap);
    if (history.stack.length > 100) history.stack.shift();
    history.index = history.stack.length - 1;
    hooks.change();
  }

  function restore(snapshot) {
    fromIR(JSON.parse(snapshot), { keepHistory: true });
    hooks.change();
  }

  function undo() {
    clearTimeout(commitTimer);
    commit();
    if (history.index > 0) { history.index -= 1; restore(history.stack[history.index]); }
  }

  function redo() {
    if (history.index < history.stack.length - 1) { history.index += 1; restore(history.stack[history.index]); }
  }

  /* ================= errors ================= */
  function clearErrors() {
    nodes.forEach((n) => n.el.classList.remove("node-error"));
  }

  function markErrors(ids) {
    clearErrors();
    (ids || []).forEach((nid) => {
      if (!nid) return;
      const n = nodes.get(String(nid).replace(/^n/, ""));
      if (n) n.el.classList.add("node-error");
    });
  }

  /* ================= view: zoom, pan, fit ================= */
  function applyView() {
    world.style.transform = `translate(${view.x}px, ${view.y}px) scale(${view.z})`;
    hooks.zoom(view.z);
  }

  function clientToWorld(cx, cy) {
    const r = container.getBoundingClientRect();
    return [(cx - r.left - view.x) / view.z, (cy - r.top - view.y) / view.z];
  }

  function zoomAt(z, cx, cy) {
    z = Math.max(0.3, Math.min(1.6, z));
    const r = container.getBoundingClientRect();
    const mx = cx - r.left, my = cy - r.top;
    view.x = mx - ((mx - view.x) * z) / view.z;
    view.y = my - ((my - view.y) * z) / view.z;
    view.z = z;
    applyView();
  }

  function zoomBy(delta) {
    const r = container.getBoundingClientRect();
    zoomAt(view.z + delta, r.left + r.width / 2, r.top + r.height / 2);
  }

  function fit() {
    if (!nodes.size) { view = { x: 0, y: 0, z: 1 }; applyView(); return; }
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    nodes.forEach((n) => {
      const b = obstacleBox(n);
      minX = Math.min(minX, b.l); minY = Math.min(minY, b.t); maxX = Math.max(maxX, b.r); maxY = Math.max(maxY, b.b);
    });
    const pad = 40, cw = container.clientWidth, ch = container.clientHeight;
    const w = maxX - minX + 120, h = maxY - minY + 20;
    const z = Math.max(0.3, Math.min(1, (cw - 2 * pad) / w, (ch - 2 * pad) / h));
    view.z = z;
    view.x = (cw - (maxX - minX) * z) / 2 - minX * z;
    view.y = pad - minY * z;
    applyView();
  }

  function focusNode(nid) {
    const n = nodes.get(String(nid).replace(/^n/, ""));
    if (!n) return;
    const b = nodeBox(n);
    view.x = container.clientWidth / 2 - ((b.l + b.r) / 2) * view.z;
    view.y = container.clientHeight / 3 - b.t * view.z;
    applyView();
  }

  /* ================= mouse interaction ================= */
  function startConnect(n, side) {
    if (n.type === "end") { hooks.notify("The End block has no outgoing arrow.", true); return; }
    selectNode(n.id);
    const temp = svgEl("path", { class: "fc-temp" });
    svg.appendChild(temp);
    container.classList.add("connecting");
    drag = { kind: "connect", n, side, temp, hover: null };
  }

  function startNodeDrag(n, e) {
    const w = clientToWorld(e.clientX, e.clientY);
    drag = { kind: "node", n, ox: n.x, oy: n.y, sx: w[0], sy: w[1], moved: false };
  }

  function onMove(e) {
    if (!drag) return;
    if (drag.kind === "pan") {
      view.x = drag.vx + (e.clientX - drag.cx);
      view.y = drag.vy + (e.clientY - drag.cy);
      applyView();
    } else if (drag.kind === "node") {
      const w = clientToWorld(e.clientX, e.clientY);
      const dx = w[0] - drag.sx, dy = w[1] - drag.sy;
      if (!drag.moved && Math.hypot(dx, dy) < 3) return;
      drag.moved = true;
      drag.n.x = Math.round(drag.ox + dx);
      drag.n.y = Math.round(drag.oy + dy);
      positionNode(drag.n);
      edgesOf(drag.n.id).forEach(renderEdge);
    } else if (drag.kind === "connect") {
      const w = clientToWorld(e.clientX, e.clientY);
      const P = portPoint(drag.n, drag.side);
      const facing = Math.abs(w[0] - P[0]) > Math.abs(w[1] - P[1]) ? (w[0] > P[0] ? "left" : "right") : (w[1] > P[1] ? "top" : "bottom");
      const pts = route(P, drag.side, w, facing);
      drag.temp.setAttribute("d", "M " + pts.map((p) => p[0] + " " + p[1]).join(" L "));
      const over = document.elementFromPoint(e.clientX, e.clientY);
      const port = over && over.closest ? over.closest(".fc-port") : null;
      if (drag.hover && drag.hover !== port) drag.hover.classList.remove("drop");
      drag.hover = port;
      if (port) port.classList.add("drop");
    }
  }

  function onUp(e) {
    window.removeEventListener("mousemove", onMove);
    window.removeEventListener("mouseup", onUp);
    const d = drag;
    drag = null;
    if (!d) return;
    if (d.kind === "node") {
      if (d.moved) scheduleCommit();
    } else if (d.kind === "connect") {
      d.temp.remove();
      container.classList.remove("connecting");
      if (d.hover) d.hover.classList.remove("drop");
      const over = document.elementFromPoint(e.clientX, e.clientY);
      const nodeEl = over && over.closest ? over.closest(".fc-node") : null;
      if (!nodeEl) return;
      const dst = nodes.get(nodeEl.dataset.id);
      const port = over.closest(".fc-port");
      const P = portPoint(d.n, d.side);
      const tS = port ? port.dataset.side : autoSide(dst, P);
      const edge = tryConnect(d.n, d.side, dst, tS);
      if (edge) selectEdge(edge.id);
    }
  }

  function onDown(e) {
    if (e.button !== 0) return;
    if (e.target.closest(".fc-note-badge, .fc-note-close, .fc-note-act")) return;
    const port = e.target.closest(".fc-port");
    const nodeEl = e.target.closest(".fc-node");
    if (port && nodeEl) {
      e.preventDefault();
      container.focus();
      startConnect(nodes.get(nodeEl.dataset.id), port.dataset.side);
    } else if (nodeEl) {
      if (document.activeElement && document.activeElement !== container && document.activeElement.blur) document.activeElement.blur();
      container.focus();
      const n = nodes.get(nodeEl.dataset.id);
      selectNode(n.id);
      startNodeDrag(n, e);
      e.preventDefault();
    } else if (e.target.closest(".fc-label, .fc-del")) {
      return;
    } else {
      container.focus();
      clearSelection();
      drag = { kind: "pan", cx: e.clientX, cy: e.clientY, vx: view.x, vy: view.y };
      e.preventDefault();
    }
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }

  /* ================= init ================= */
  function init(el, callbacks) {
    container = el;
    Object.assign(hooks, callbacks || {});
    container.classList.add("fc-viewport");
    container.tabIndex = 0;
    world = document.createElement("div");
    world.className = "fc-world";
    svg = svgEl("svg", { class: "fc-edges" });
    ui = document.createElement("div");
    ui.className = "fc-ui";
    delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.className = "fc-del";
    delBtn.title = "Delete this arrow";
    delBtn.setAttribute("aria-label", "Delete this arrow");
    delBtn.textContent = "\u00d7";
    delBtn.hidden = true;
    delBtn.addEventListener("mousedown", (e) => e.stopPropagation());
    delBtn.addEventListener("click", (e) => { e.stopPropagation(); deleteSelected(); });
    ui.appendChild(delBtn);
    world.append(svg, ui);
    container.appendChild(world);
    applyView();

    container.addEventListener("mousedown", onDown);
    container.addEventListener("wheel", (e) => {
      e.preventDefault();
      if (e.ctrlKey) zoomAt(view.z * (e.deltaY < 0 ? 1.1 : 1 / 1.1), e.clientX, e.clientY);
      else { view.x -= e.deltaX; view.y -= e.deltaY; applyView(); }
    }, { passive: false });
    container.addEventListener("dragover", (e) => e.preventDefault());
    container.addEventListener("drop", (e) => {
      e.preventDefault();
      const type = e.dataTransfer.getData("text/plain");
      if (!SPECS[type]) return;
      const p = clientToWorld(e.clientX, e.clientY);
      addBlock(type, p[0] - SLOT / 2, p[1] - 20);
    });
    document.addEventListener("keydown", (e) => {
      if ((e.key === "Delete" || e.key === "Backspace") && sel && container.offsetParent !== null &&
          !/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName)) {
        e.preventDefault();
        deleteSelected();
      }
    });
  }

  return {
    init, addBlock, addBlockAtCenter, deleteSelected, renderProps, getData, toIR, fromIR, newDiagram,
    isEmpty, markErrors, clearErrors, focusNode, fit, undo, redo, variableNames,
    zoomIn: () => zoomBy(0.1), zoomOut: () => zoomBy(-0.1),
    selectedId: () => (sel && sel.kind === "node" ? sel.id : null), commit,
  };
})();
