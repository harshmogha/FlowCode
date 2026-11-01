"""Tiny SQLite storage for saved projects."""
import json
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "projects.db")


def _connect(path=None):
    conn = sqlite3.connect(path or DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path=None):
    with _connect(path) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS projects (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   name TEXT NOT NULL,
                   language TEXT NOT NULL DEFAULT 'python',
                   mode TEXT NOT NULL DEFAULT 'flowchart',
                   diagram_json TEXT NOT NULL,
                   algorithm_text TEXT NOT NULL DEFAULT '',
                   code TEXT NOT NULL DEFAULT '',
                   created_at TEXT NOT NULL,
                   updated_at TEXT NOT NULL)"""
        )


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def list_projects(path=None):
    with _connect(path) as conn:
        rows = conn.execute("SELECT id, name, language, updated_at FROM projects ORDER BY updated_at DESC").fetchall()
    return [dict(r) for r in rows]


def get_project(pid, path=None):
    with _connect(path) as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["diagram"] = json.loads(d.pop("diagram_json"))
    return d


def save_project(data, path=None):
    """Insert or update by id. Returns the project id."""
    now = _now()
    diagram = json.dumps(data["diagram"])
    with _connect(path) as conn:
        pid = data.get("id")
        if pid and conn.execute("SELECT 1 FROM projects WHERE id = ?", (pid,)).fetchone():
            conn.execute(
                """UPDATE projects SET name=?, language=?, mode=?, diagram_json=?, algorithm_text=?, code=?, updated_at=?
                   WHERE id=?""",
                (data["name"], data.get("language", "python"), data.get("mode", "flowchart"), diagram,
                 data.get("algorithm_text", ""), data.get("code", ""), now, pid))
            return pid
        cur = conn.execute(
            """INSERT INTO projects (name, language, mode, diagram_json, algorithm_text, code, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["name"], data.get("language", "python"), data.get("mode", "flowchart"), diagram,
             data.get("algorithm_text", ""), data.get("code", ""), now, now))
        return cur.lastrowid


def delete_project(pid, path=None):
    with _connect(path) as conn:
        conn.execute("DELETE FROM projects WHERE id = ?", (pid,))
