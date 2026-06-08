"""
SQLite persistence for AI Student OS.
Schema is normalized for future PostgreSQL migration (integer FKs, ISO timestamps).
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

_DB_PATH = Path(__file__).resolve().parent / "ai_student_os.db"
_lock = threading.Lock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_db_path() -> Path:
    return _DB_PATH


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    with _lock:
        conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def init_db() -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                display_name TEXT NOT NULL DEFAULT '',
                profile_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                task_type TEXT NOT NULL,
                title TEXT NOT NULL,
                difficulty INTEGER NOT NULL DEFAULT 2,
                status TEXT NOT NULL DEFAULT 'pending',
                due_date TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                problem_statement TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS progress_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                track TEXT NOT NULL,
                delta REAL NOT NULL DEFAULT 1,
                topic TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS focus_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
                minutes INTEGER NOT NULL,
                focus_score INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS timetables (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                week_start TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS daily_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                day TEXT NOT NULL,
                score INTEGER NOT NULL,
                breakdown_json TEXT NOT NULL,
                percentile_hint TEXT NOT NULL DEFAULT '',
                UNIQUE(user_id, day)
            );

            CREATE TABLE IF NOT EXISTS recovery_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_tasks_user_due ON tasks(user_id, due_date);
            CREATE INDEX IF NOT EXISTS idx_progress_user ON progress_events(user_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
            """
        )
        _ensure_tasks_problem_statement_column(conn)


def _ensure_tasks_problem_statement_column(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(tasks)")
    cols = {row[1] for row in cur.fetchall()}
    if cols and "problem_statement" not in cols:
        cur.execute("ALTER TABLE tasks ADD COLUMN problem_statement TEXT NOT NULL DEFAULT ''")


def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {k: row[k] for k in row.keys()}


def default_profile() -> Dict[str, Any]:
    return {
        "timezone": "UTC",
        "sleep": {"start": "23:30", "end": "06:30"},
        "fixed_blocks": [
            {"label": "College", "days": [0, 1, 2, 3, 4], "start": "09:00", "end": "16:15"}
        ],
        "optional_blocks": [{"label": "Gym", "days": [0, 2, 4], "start": "18:00", "end": "19:00"}],
        "goals": {"dsa": 10, "oop": 6, "sql": 6, "java": 8, "webdev": 6},
        "energy": "morning",
        "exam_mode": False,
        "productivity_windows": [],
    }


def load_json_field(raw: str, fallback: Dict[str, Any]) -> Dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else fallback
    except Exception:
        return fallback


def merge_profile(current: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    merged = {**default_profile(), **current}
    for key, value in patch.items():
        if value is None:
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged
