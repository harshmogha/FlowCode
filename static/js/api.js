/* Thin wrapper around fetch() for the Flask API. */
const api = (() => {
  async function request(method, url, body) {
    const options = { method, headers: {} };
    if (body !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
    let response;
    try {
      response = await fetch(url, options);
    } catch (err) {
      throw new Error("Cannot reach the server. Make sure the black run.bat window is still open (if not, double-click run.bat again), then refresh this page.");
    }
    let data = null;
    try { data = await response.json(); } catch (err) { /* not JSON */ }
    if (!response.ok && !(data && typeof data === "object")) {
      throw new Error("The server returned an error (" + response.status + ").");
    }
    return data;
  }
  return {
    generate: (ir, language) => request("POST", "/api/generate", { ir, language }),
    run: (code, stdin) => request("POST", "/api/run", { code, stdin }),
    runStart: (code) => request("POST", "/api/run/start", { code }),
    runPoll: (id, since) => request("GET", "/api/run/" + id + "/poll?since=" + since),
    runInput: (id, text) => request("POST", "/api/run/" + id + "/input", { text }),
    runStop: (id) => request("POST", "/api/run/" + id + "/stop", {}),
    parseAlgorithm: (text) => request("POST", "/api/parse-algorithm", { text }),
    toAlgorithm: (ir) => request("POST", "/api/to-algorithm", { ir }),
    examples: () => request("GET", "/api/examples"),
    aiStatus: () => request("GET", "/api/ai-status"),
    formulaPreview: (text, kind, variables) => request("POST", "/api/formula-preview", { text, kind, variables }),
    aiSettings: () => request("GET", "/api/ai/settings"),
    saveAiSettings: (settings) => request("POST", "/api/ai/settings", settings),
    aiModels: () => request("GET", "/api/ai/models"),
    startOllama: () => request("POST", "/api/ai/start", {}),
    deleteModel: (name) => request("POST", "/api/ai/delete", { name }),
    async pullModel(name, onProgress) {
      let response;
      try {
        response = await fetch("/api/ai/pull", {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }),
        });
      } catch (err) { throw new Error("Cannot reach the server."); }
      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error((data && data.error) || "The download could not start.");
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let nl;
        while ((nl = buffer.indexOf("\n")) >= 0) {
          const line = buffer.slice(0, nl).trim();
          buffer = buffer.slice(nl + 1);
          if (!line) continue;
          const obj = JSON.parse(line);
          if (obj.error) throw new Error(obj.error);
          onProgress(obj);
        }
      }
    },
    projects: () => request("GET", "/api/projects"),
    getProject: (id) => request("GET", "/api/projects/" + id),
    saveProject: (project) => request("POST", "/api/projects", project),
    deleteProject: (id) => request("DELETE", "/api/projects/" + id),
  };
})();
