"""FlowCode - Flask application."""
import json

from flask import Flask, Response, jsonify, render_template, request, stream_with_context

from database import db
from services import ai_provider, ai_settings
from services import formula_preview as formula_preview_service
from services.algorithm_text import check_algorithm, describe_steps, parse_algorithm, safe_print
from services.code_generator import GenerationError, generate_python
from services.examples import EXAMPLES
from services.executor import run_python
from services.interactive import RunManager
from services.flow_validator import validate_ir
from services.structure import StructureError


def create_app(db_path=None):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024  # 1 MB request limit
    db.init_db(db_path)
    runs = RunManager()

    def body():
        data = request.get_json(silent=True)
        return data if isinstance(data, dict) else {}

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/examples")
    def examples():
        out = []
        for ex in EXAMPLES:
            parsed = parse_algorithm(ex["text"])
            out.append({"name": ex["name"], "text": ex["text"], "ir": parsed["ir"]})
        return jsonify(out)

    @app.get("/api/ai-status")
    def ai_status():
        return jsonify(ai_provider.status())

    @app.get("/api/ai/settings")
    def get_ai_settings():
        return jsonify(ai_settings.public())

    @app.post("/api/ai/settings")
    def set_ai_settings():
        ok, message = ai_settings.save(body())
        status = 200 if ok else 400
        return jsonify({"ok": ok, "message": message, "settings": ai_settings.public(),
                        "status": ai_provider.status() if ok else None}), status

    @app.get("/api/ai/models")
    def ai_models():
        s = ai_settings.load()
        running, error = True, ""
        try:
            models = ai_provider.ollama_models()
        except ai_provider.AIError as ex:
            running, error = False, str(ex)
            # Ollama is off: still show the models that are already downloaded on this computer.
            models = ai_provider.disk_models() if ai_provider.is_local_url(s["ollama_url"]) else []
        return jsonify({"ok": True, "running": running, "error": error, "models": models,
                        "selected": s["ollama_model"], "provider": s["provider"], "status": ai_provider.status()})

    @app.post("/api/ai/start")
    def ai_start():
        try:
            message = ai_provider.start_ollama()
        except ai_provider.AIError as ex:
            return jsonify({"ok": False, "error": str(ex)})
        return jsonify({"ok": True, "message": message})
    @app.post("/api/ai/pull")
    def ai_pull():
        name = str(body().get("name", "")).strip()
        if not ai_settings.MODEL_NAME_RE.match(name):
            return jsonify({"ok": False, "error": "Enter a model name like qwen2.5-coder:7b."}), 400

        def stream():
            try:
                for line in ai_provider.pull_model_stream(name):
                    yield line + "\n"
            except ai_provider.AIError as ex:
                yield json.dumps({"error": str(ex)}) + "\n"

        return Response(stream_with_context(stream()), mimetype="application/x-ndjson")

    @app.post("/api/ai/delete")
    def ai_delete():
        name = str(body().get("name", "")).strip()
        if not ai_settings.MODEL_NAME_RE.match(name):
            return jsonify({"ok": False, "error": "Invalid model name."}), 400
        try:
            ai_provider.delete_model(name)
        except ai_provider.AIError as ex:
            return jsonify({"ok": False, "error": str(ex)})
        return jsonify({"ok": True})

    @app.post("/api/formula-preview")
    def formula_preview():
        data = body()
        kind = data.get("kind") if data.get("kind") in ("expression", "condition", "list", "note") else "expression"
        variables = [v for v in data.get("variables", []) if isinstance(v, str)][:200]
        return jsonify(formula_preview_service.preview(str(data.get("text", ""))[:2000], kind, variables))

    @app.post("/api/validate")
    def validate():
        return jsonify(validate_ir(body().get("ir")))

    @app.post("/api/generate")
    def generate():
        data = body()
        ir, language = data.get("ir"), data.get("language", "python")
        check = validate_ir(ir)
        if not check["valid"]:
            return jsonify({"ok": False, "errors": check["errors"]}), 200
        try:
            python_code = generate_python(ir)
            steps = describe_steps(ir)
        except (GenerationError, StructureError) as ex:
            errors = getattr(ex, "errors", None) or [{"nodeId": getattr(ex, "node_id", None), "message": str(ex)}]
            return jsonify({"ok": False, "errors": errors})
        result = {"ok": True, "code": python_code, "steps": steps, "language": language, "note": ""}
        if language != "python":
            if language not in ai_provider.LANGUAGES:
                return jsonify({"ok": False, "errors": [{"nodeId": None, "message": "Unsupported language."}]})
            steps_text = "\n".join(f"{i + 1}. {'  ' * s['depth']}{s['text']}" for i, s in enumerate(steps))
            try:
                result["code"] = ai_provider.translate(language, python_code, steps_text)
                result["note"] = "Generated by the AI model from the flowchart (check it before use)."
            except ai_provider.AIError as ex:
                result["ok"] = False
                result["errors"] = [{"nodeId": None, "message": str(ex)}]
                result["fallbackCode"] = python_code
        return jsonify(result)

    @app.post("/api/run")
    def run():
        data = body()
        code = data.get("code")
        if not isinstance(code, str) or not code.strip():
            return jsonify({"ok": False, "stdout": "", "stderr": "There is no code to run.", "timedOut": False})
        return jsonify(run_python(code, str(data.get("stdin", ""))))

    # ---- console-style runs: the program pauses at input() and waits for a typed value ----
    @app.post("/api/run/start")
    def run_start():
        code = body().get("code")
        if not isinstance(code, str) or not code.strip():
            return jsonify({"ok": False, "error": "There is no code to run."})
        run, problem = runs.start(code)
        if problem:
            return jsonify({"ok": False, "error": problem})
        return jsonify({"ok": True, "id": run.id})

    @app.get("/api/run/<rid>/poll")
    def run_poll(rid):
        run = runs.get(rid)
        if not run:
            return jsonify({"ok": False, "error": "This run no longer exists."}), 404
        since = request.args.get("since", "0")
        result = run.snapshot(int(since) if since.isdigit() else 0)
        result["ok"] = True
        return jsonify(result)

    @app.post("/api/run/<rid>/input")
    def run_input(rid):
        run = runs.get(rid)
        if not run:
            return jsonify({"ok": False, "error": "This run no longer exists."}), 404
        return jsonify({"ok": run.send_input(str(body().get("text", "")))})

    @app.post("/api/run/<rid>/stop")
    def run_stop(rid):
        run = runs.get(rid)
        if run:
            run.stop()
        return jsonify({"ok": True})

    @app.post("/api/parse-algorithm")
    def parse_alg():
        result = check_algorithm(str(body().get("text", "")))
        return jsonify(result)

    @app.post("/api/to-algorithm")
    def to_alg():
        text, err = safe_print(body().get("ir") or {})
        if err:
            return jsonify({"ok": False, "error": err})
        return jsonify({"ok": True, "text": text})

    @app.get("/api/projects")
    def projects():
        return jsonify(db.list_projects(db_path))

    @app.post("/api/projects")
    def save_project():
        data = body()
        name = str(data.get("name", "")).strip()[:100]
        if not name or not isinstance(data.get("diagram"), dict):
            return jsonify({"ok": False, "error": "A project name and diagram are required."}), 400
        data["name"] = name
        pid = db.save_project(data, db_path)
        return jsonify({"ok": True, "id": pid})

    @app.get("/api/projects/<int:pid>")
    def get_project(pid):
        project = db.get_project(pid, db_path)
        if not project:
            return jsonify({"ok": False, "error": "Project not found."}), 404
        return jsonify({"ok": True, "project": project})

    @app.delete("/api/projects/<int:pid>")
    def delete_project(pid):
        db.delete_project(pid, db_path)
        return jsonify({"ok": True})

    @app.errorhandler(413)
    def too_large(_):
        return jsonify({"ok": False, "error": "The request is too large."}), 413

    return app


if __name__ == "__main__":
    import os
    create_app().run(host="127.0.0.1", port=int(os.environ.get("FLOWCODE_PORT", "5000")), debug=False)
