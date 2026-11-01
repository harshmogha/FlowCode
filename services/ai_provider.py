"""Optional AI code generation for languages other than Python.

The deterministic Python generator is the reference. For Java / C++ the
reference Python program and the algorithm steps are given to a model, which
only has to translate them. Settings come from the AI Settings dialog
(services/ai_settings.py) and fall back to environment variables:

    AI_PROVIDER, OLLAMA_URL, OLLAMA_MODEL, OPENAI_BASE_URL, OPENAI_API_KEY, OPENAI_MODEL
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from . import ai_settings

LANGUAGES = {"python": "Python", "java": "Java", "cpp": "C++"}

# Preferred local models, best first (substring match on the installed model name).
MODEL_PREFERENCE = ("qwen2.5-coder", "coder", "codellama", "deepseek", "qwen2.5", "qwen3", "llama3", "gemma", "mistral", "phi")
NOT_CHAT_MODELS = ("embed", "bge", "minilm")

SYSTEM_PROMPT = (
    "You are a precise code translator. You receive an algorithm (as numbered steps and as a "
    "reference Python program). Write the same program in the requested language. "
    "Follow the reference exactly: same variable names, same input prompts, same output text, "
    "same logic and keep every comment. Do not add features. Return only one fenced code block, no explanation."
)


class AIError(Exception):
    pass


def _open(url, payload=None, headers=None, timeout=120, method=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json", **(headers or {})},
        method=method or ("POST" if payload is not None else "GET"))
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as ex:
        try:
            detail = json.loads(ex.read().decode("utf-8")).get("error", "")
        except Exception:
            detail = ""
        raise AIError(f"The AI service returned an error ({ex.code}). {detail}".strip())
    except urllib.error.URLError as ex:
        raise AIError(f"Could not reach the AI service ({ex.reason}).")
    except TimeoutError as ex:
        raise AIError(f"The AI service took too long to answer ({ex}).")


def _request(url, payload=None, headers=None, timeout=120, method=None):
    with _open(url, payload, headers, timeout, method) as resp:
        raw = resp.read().decode("utf-8")
    try:
        return json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as ex:
        raise AIError(f"The AI service did not answer correctly ({ex}).")


# ------------------------------------------------------------ Ollama management
def is_local_url(url):
    return (urlparse(url).hostname or "") in ("127.0.0.1", "localhost", "::1")


def _usable(name):
    return not any(k in name.lower() for k in NOT_CHAT_MODELS) and not name.endswith(":cloud")


def disk_models():
    """Models already downloaded, read from Ollama's folder (works even when Ollama is not running)."""
    root = Path(os.environ.get("OLLAMA_MODELS") or Path.home() / ".ollama" / "models") / "manifests"
    out = []
    if not root.is_dir():
        return out
    for f in root.rglob("*"):
        if not f.is_file():
            continue
        parts = f.relative_to(root).parts            # host / namespace / model / tag
        if len(parts) != 4:
            continue
        host, namespace, model, tag = parts
        if host == "registry.ollama.ai":
            name = f"{model}:{tag}" if namespace == "library" else f"{namespace}/{model}:{tag}"
        else:
            name = f"{host}/{namespace}/{model}:{tag}"
        try:
            manifest = json.loads(f.read_text(encoding="utf-8"))
            size = sum(l.get("size", 0) for l in (manifest.get("layers") or [])) + (manifest.get("config") or {}).get("size", 0)
        except (OSError, ValueError, TypeError, AttributeError):
            size = 0
        out.append({"name": name, "size": size, "usable": _usable(name)})
    return sorted(out, key=lambda m: m["name"])


def find_ollama_exe():
    exe = shutil.which("ollama")
    if exe:
        return exe
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidate = Path(local) / "Programs" / "Ollama" / "ollama.exe"
        if candidate.is_file():
            return str(candidate)
    return None


def start_ollama():
    """Start `ollama serve` in the background (local address only) and wait until it answers."""
    s = ai_settings.load()
    if not is_local_url(s["ollama_url"]):
        raise AIError("Ollama is set to a remote address, so it cannot be started from here.")
    try:
        ollama_models()
        return "Ollama is already running."
    except AIError:
        pass
    exe = find_ollama_exe()
    if not exe:
        raise AIError("Ollama is not installed. Download it from https://ollama.com/download")
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    subprocess.Popen([exe, "serve"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, creationflags=flags)
    for _ in range(20):
        time.sleep(0.5)
        try:
            ollama_models()
            return "Ollama started."
        except AIError:
            continue
    raise AIError("Ollama was launched but is not answering yet. Wait a few seconds and press Refresh.")

def ollama_models():
    """Installed models: [{name, size, usable}]."""
    s = ai_settings.load()
    data = _request(f"{s['ollama_url']}/api/tags", timeout=5)
    out = []
    for m in data.get("models", []):
        name = m.get("name")
        if not name:
            continue
        out.append({"name": name, "size": m.get("size", 0), "usable": _usable(name)})
    return out


def pick_ollama_model(names):
    """Choose a usable chat model from installed names (skips embedding and cloud models)."""
    usable = [n for n in names if not any(k in n.lower() for k in NOT_CHAT_MODELS) and not n.endswith(":cloud")]
    for pref in MODEL_PREFERENCE:
        for n in usable:
            if pref in n.lower():
                return n
    return usable[0] if usable else None


def pull_model_stream(name):
    """Yield Ollama's progress lines (JSON text) while downloading a model."""
    s = ai_settings.load()
    resp = _open(f"{s['ollama_url']}/api/pull", {"model": name, "name": name, "stream": True}, timeout=900)
    with resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if line:
                yield line


def delete_model(name):
    s = ai_settings.load()
    _request(f"{s['ollama_url']}/api/delete", {"model": name, "name": name}, method="DELETE", timeout=30)


# ---------------------------------------------------------------- status & use
def status():
    """Describe the AI connection for the UI: {connected, provider, model, message}."""
    s = ai_settings.load()
    if s["provider"] == "openai":
        if not s["openai_api_key"]:
            return {"connected": False, "provider": "openai", "model": s["openai_model"],
                    "message": "Online AI needs an API key. Open AI Settings and enter one."}
        return {"connected": True, "provider": "openai", "model": s["openai_model"],
                "message": f"Online model configured ({s['openai_model']}). It is tested when you generate."}
    try:
        names = [m["name"] for m in ollama_models()]
    except AIError:
        return {"connected": False, "provider": "ollama", "model": None,
                "message": "Ollama is not running. Start the Ollama app (or run: ollama serve)."}
    chosen = s["ollama_model"]
    if chosen:
        if chosen not in names:
            return {"connected": False, "provider": "ollama", "model": chosen,
                    "message": f"Model '{chosen}' is not installed. Download it in AI Settings."}
        return {"connected": True, "provider": "ollama", "model": chosen, "message": f"Connected to Ollama ({chosen})."}
    model = pick_ollama_model(names)
    if not model:
        return {"connected": False, "provider": "ollama", "model": None,
                "message": "Ollama is running but has no chat model. Download one in AI Settings."}
    return {"connected": True, "provider": "ollama", "model": model, "message": f"Connected to Ollama ({model}, chosen automatically)."}


def _complete(system, user):
    s = ai_settings.load()
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    if s["provider"] == "openai":
        if not s["openai_api_key"]:
            raise AIError("Online AI needs an API key. Open AI Settings and enter one.")
        data = _request(f"{s['openai_base_url']}/chat/completions",
                        {"model": s["openai_model"], "temperature": 0, "messages": messages},
                        {"Authorization": f"Bearer {s['openai_api_key']}"})
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            raise AIError("Unexpected answer from the AI service.")
    st = status()
    if not st["connected"]:
        raise AIError(st["message"])
    data = _request(f"{s['ollama_url']}/api/chat",
                    {"model": st["model"], "stream": False, "options": {"temperature": 0}, "messages": messages})
    try:
        return data["message"]["content"]
    except KeyError:
        raise AIError("Unexpected answer from the AI service.")


def extract_code(text: str) -> str:
    m = re.search(r"```[a-zA-Z+#]*\n(.*?)```", text, re.S)
    return (m.group(1) if m else text).strip() + "\n"


def translate(language: str, python_code: str, steps_text: str) -> str:
    if language not in LANGUAGES or language == "python":
        raise AIError("Unsupported language.")
    user = (f"Target language: {LANGUAGES[language]}\n\nAlgorithm steps:\n{steps_text}\n\n"
            f"Reference Python program:\n```python\n{python_code}```\n")
    return extract_code(_complete(SYSTEM_PROMPT, user))
