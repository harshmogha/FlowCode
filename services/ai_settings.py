"""AI settings saved by the Settings dialog (falls back to environment variables).

The file lives in database/ai_settings.json and may contain an API key, so it is
git-ignored. The key is never sent back to the browser.
"""
import json
import os
import re
from urllib.parse import urlparse

PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "ai_settings.json")
PROVIDERS = ("ollama", "openai")
MODEL_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/\-]{0,99}$")


def _read():
    try:
        with open(PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def load():
    """Effective settings: saved file first, then environment, then defaults."""
    saved = _read()
    env = os.environ.get
    provider = (saved.get("provider") or env("AI_PROVIDER") or "ollama").lower()
    return {
        "provider": provider if provider in PROVIDERS else "ollama",
        "ollama_url": (saved.get("ollama_url") or env("OLLAMA_URL") or "http://127.0.0.1:11434").rstrip("/"),
        "ollama_model": saved["ollama_model"] if "ollama_model" in saved else (env("OLLAMA_MODEL") or ""),
        "openai_base_url": (saved.get("openai_base_url") or env("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/"),
        "openai_model": saved.get("openai_model") or env("OPENAI_MODEL") or "gpt-4o-mini",
        "openai_api_key": saved.get("openai_api_key") or env("OPENAI_API_KEY") or "",
    }


def public():
    """Settings that are safe to show in the browser (no secret key)."""
    s = load()
    key = s.pop("openai_api_key")
    s["has_api_key"] = bool(key)
    return s


def _valid_url(url):
    p = urlparse(url)
    return p.scheme in ("http", "https") and bool(p.netloc)


def save(new):
    """Validate and store settings. Returns (ok, message)."""
    current = _read()
    updates = {}
    if "provider" in new:
        if new["provider"] not in PROVIDERS:
            return False, "Unknown provider."
        updates["provider"] = new["provider"]
    for key in ("ollama_url", "openai_base_url"):
        if key in new:
            url = str(new[key]).strip().rstrip("/")
            if not _valid_url(url):
                return False, "The address must start with http:// or https://"
            updates[key] = url
    if "ollama_model" in new:
        name = str(new["ollama_model"]).strip()
        if name and not MODEL_NAME_RE.match(name):
            return False, "That model name is not valid."
        updates["ollama_model"] = name          # empty string = automatic choice
    if "openai_model" in new:
        name = str(new["openai_model"]).strip()
        if not name or len(name) > 100:
            return False, "Enter the online model name."
        updates["openai_model"] = name
    if new.get("openai_api_key"):                # empty = keep the key already saved
        updates["openai_api_key"] = str(new["openai_api_key"]).strip()
    if new.get("clear_api_key"):
        updates["openai_api_key"] = ""
    current.update(updates)
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)
    return True, "Settings saved."
