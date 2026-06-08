"""
FastAPI routes for AI Student OS (auth, timetable, tasks, analytics, mentor chat).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import sqlite3

from fastapi import APIRouter, Body, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from student_os_db import (
    _utc_now,
    default_profile,
    get_connection,
    init_db,
    load_json_field,
    merge_profile,
    row_to_dict,
)
from student_os_engine import (
    anti_procrastination_prompt,
    compute_discipline_score,
    detect_burnout,
    generate_weekly_timetable,
    recovery_plan,
    shadow_projection,
    suggest_daily_tasks,
)

router = APIRouter()
init_db()
_mentor_client = None


@router.get("/health")
def health_check():
    return {"status": "ok", "service": "ai-student-os"}


# --- Auth helpers ---

def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"{salt}${dk.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, hashed = stored.split("$", 1)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
        return dk.hex() == hashed
    except Exception:
        return False


def _week_start(today: date) -> date:
    return today - timedelta(days=today.weekday())


def _today_iso(user_tz: str) -> str:
    # Store analytics in UTC date for consistency; client may adjust display.
    return datetime.now(timezone.utc).date().isoformat()


def get_user_from_token(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Invalid token")

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT u.id, u.username, u.display_name, u.profile_json
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = ? AND s.expires_at > ?
            """,
            (token, _utc_now()),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="Session expired or invalid")

        user = row_to_dict(row)
        user["profile"] = merge_profile(default_profile(), load_json_field(user.pop("profile_json"), {}))
        user["token"] = token
        return user


# --- Models ---

class SignupRequest(BaseModel):
    """Lengths checked again after strip so spaces do not satisfy min_length."""
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)
    display_name: str = Field(default="", max_length=80)


class LoginRequest(BaseModel):
    username: str
    password: str


class ProfileUpdate(BaseModel):
    timezone: Optional[str] = None
    sleep: Optional[Dict[str, str]] = None
    fixed_blocks: Optional[List[Dict[str, Any]]] = None
    optional_blocks: Optional[List[Dict[str, Any]]] = None
    goals: Optional[Dict[str, Any]] = None
    energy: Optional[str] = None
    exam_mode: Optional[bool] = None
    productivity_windows: Optional[List[Dict[str, Any]]] = None


class TaskCreate(BaseModel):
    task_type: str
    title: str
    difficulty: int = 2
    due_date: str
    notes: str = ""
    problem_statement: str = ""


class TaskPatch(BaseModel):
    status: str


class ProgressLog(BaseModel):
    track: str
    delta: float = 1.0
    topic: str = ""


class FocusSessionCreate(BaseModel):
    minutes: int = Field(ge=1, le=240)
    task_id: Optional[int] = None


class MentorChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class NudgePing(BaseModel):
    idle_minutes: int = Field(ge=0, le=24 * 60)


# --- Routes ---

@router.post("/auth/signup")
def signup(payload: SignupRequest):
    username = payload.username.strip().lower()
    if len(username) < 3:
        raise HTTPException(
            status_code=400,
            detail="Username must be at least 3 characters (after trimming spaces).",
        )
    if len(payload.password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters.")
    display = payload.display_name.strip() or payload.username.strip()
    pw_hash = _hash_password(payload.password)
    now = _utc_now()
    profile_dict = default_profile()
    profile = json.dumps(profile_dict)

    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO users (username, password_hash, display_name, profile_json, created_at) VALUES (?,?,?,?,?)",
                (username, pw_hash, display, profile, now),
            )
            user_id = cur.lastrowid
            token = secrets.token_urlsafe(32)
            expires = (datetime.now(timezone.utc) + timedelta(days=21)).replace(microsecond=0).isoformat()
            cur.execute(
                "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?,?,?,?)",
                (token, user_id, now, expires),
            )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=400, detail="Username already exists") from exc

    return {
        "status": "ok",
        "token": token,
        "user": {
            "id": user_id,
            "username": username,
            "display_name": display,
            "profile": profile_dict,
        },
    }


@router.post("/auth/login")
def login(payload: LoginRequest):
    username = payload.username.strip().lower()
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, password_hash, display_name, profile_json FROM users WHERE username = ?",
            (username,),
        )
        row = cur.fetchone()
        if not row or not _verify_password(payload.password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        user_id = row["id"]
        now = _utc_now()
        token = secrets.token_urlsafe(32)
        expires = (datetime.now(timezone.utc) + timedelta(days=21)).replace(microsecond=0).isoformat()
        cur.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?,?,?,?)",
            (token, user_id, now, expires),
        )

        profile = merge_profile(default_profile(), load_json_field(row["profile_json"], {}))
        return {
            "status": "ok",
            "token": token,
            "user": {"id": user_id, "username": username, "display_name": row["display_name"], "profile": profile},
        }


@router.get("/me")
def me(user: Dict[str, Any] = Depends(get_user_from_token)):
    user.pop("token", None)
    return {"status": "ok", "user": user}


@router.put("/profile")
def update_profile(payload: ProfileUpdate, user: Dict[str, Any] = Depends(get_user_from_token)):
    patch = {k: v for k, v in payload.model_dump().items() if v is not None}
    merged = merge_profile(user["profile"], patch)

    with get_connection() as conn:
        conn.cursor().execute(
            "UPDATE users SET profile_json = ? WHERE id = ?",
            (json.dumps(merged), user["id"]),
        )
    return {"status": "ok", "profile": merged}


@router.post("/timetable/generate")
def timetable_generate(user: Dict[str, Any] = Depends(get_user_from_token)):
    today = datetime.now(timezone.utc).date()
    start = _week_start(today)
    plan = generate_weekly_timetable(user["profile"], start)

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM timetables WHERE user_id = ? AND week_start = ?", (user["id"], start.isoformat()))
        cur.execute(
            "INSERT INTO timetables (user_id, week_start, payload_json, created_at) VALUES (?,?,?,?)",
            (user["id"], start.isoformat(), json.dumps(plan), _utc_now()),
        )
    return {"status": "ok", "timetable": plan}


@router.get("/timetable")
def timetable_get(user: Dict[str, Any] = Depends(get_user_from_token)):
    start = _week_start(datetime.now(timezone.utc).date())
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT payload_json FROM timetables WHERE user_id = ? AND week_start = ? ORDER BY id DESC LIMIT 1",
            (user["id"], start.isoformat()),
        )
        row = cur.fetchone()
    if not row:
        plan = generate_weekly_timetable(user["profile"], start)
        return {"status": "ok", "timetable": plan, "persisted": False}
    return {"status": "ok", "timetable": json.loads(row["payload_json"]), "persisted": True}


_ALLOWED_SLOT_CATEGORIES = frozenset({"fixed", "optional", "study", "break", "revision"})


@router.put("/timetable")
def timetable_put(plan: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(get_user_from_token)):
    """Replace the current week's stored timetable (same week anchor as GET /timetable)."""
    days = plan.get("days")
    if not isinstance(days, list) or len(days) != 7:
        raise HTTPException(status_code=400, detail="Timetable must include exactly 7 days.")

    start = _week_start(datetime.now(timezone.utc).date())
    clean_days: List[Dict[str, Any]] = []

    for i, day in enumerate(days):
        if not isinstance(day, dict):
            raise HTTPException(status_code=400, detail=f"Invalid day object at index {i}.")
        tl = day.get("timeline")
        if not isinstance(tl, list):
            raise HTTPException(status_code=400, detail=f"Day {i} must have a timeline array.")

        clean_timeline: List[Dict[str, Any]] = []
        for j, slot in enumerate(tl):
            if not isinstance(slot, dict):
                raise HTTPException(status_code=400, detail=f"Invalid slot at day {i}, index {j}.")
            for key in ("start", "end", "label", "category"):
                if key not in slot:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Slot at day {i}, index {j} must include start, end, label, and category.",
                    )
            cat = str(slot.get("category", "study")).strip().lower()
            if cat not in _ALLOWED_SLOT_CATEGORIES:
                cat = "study"
            entry: Dict[str, Any] = {
                "start": str(slot.get("start", "")).strip(),
                "end": str(slot.get("end", "")).strip(),
                "label": str(slot.get("label", "")).strip(),
                "category": cat,
            }
            intensity = slot.get("intensity")
            if intensity is not None and str(intensity).strip():
                entry["intensity"] = str(intensity).strip()
            clean_timeline.append(entry)

        clean_day: Dict[str, Any] = {
            "index": int(day.get("index", i)),
            "name": str(day.get("name", "")),
            "date": str(day.get("date", "")),
            "timeline": clean_timeline,
        }
        if "free_minutes" in day:
            try:
                clean_day["free_minutes"] = int(day["free_minutes"])
            except (TypeError, ValueError):
                pass
        if isinstance(day.get("topic_mix"), dict):
            clean_day["topic_mix"] = day["topic_mix"]
        if isinstance(day.get("revision"), dict):
            clean_day["revision"] = day["revision"]
        clean_days.append(clean_day)

    meta_in = plan.get("meta")
    meta: Dict[str, Any] = dict(meta_in) if isinstance(meta_in, dict) else {}
    out = {
        "week_start": start.isoformat(),
        "days": clean_days,
        "meta": meta,
    }

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM timetables WHERE user_id = ? AND week_start = ?", (user["id"], start.isoformat()))
        cur.execute(
            "INSERT INTO timetables (user_id, week_start, payload_json, created_at) VALUES (?,?,?,?)",
            (user["id"], start.isoformat(), json.dumps(out), _utc_now()),
        )
    return {"status": "ok", "timetable": out, "persisted": True}


def _llm_complete(system: str, user_prompt: str) -> str:
    try:
        backend_module = sys.modules.get("backend")
        if backend_module is None:
            import backend as backend_module  # type: ignore

        request_completion = getattr(backend_module, "request_completion", None) if backend_module else None
        if callable(request_completion):
            return (request_completion(system, user_prompt, temperature=0.45) or "").strip()
    except Exception:
        pass

    global _mentor_client
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return ""
    try:
        if _mentor_client is None:
            from groq import Groq

            _mentor_client = Groq(api_key=api_key)
        response = _mentor_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.45,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception:
        return ""


def _clean_message_tokens(message: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9+#.-]+", (message or "").lower())


def _topic_focus_lines(progress: List[Dict[str, Any]]) -> List[str]:
    topic_counts: Dict[str, int] = {}
    for item in progress:
        name = str(item.get("topic") or item.get("track") or "").strip()
        if not name:
            continue
        topic_counts[name] = topic_counts.get(name, 0) + 1
    ordered = sorted(topic_counts.items(), key=lambda pair: (-pair[1], pair[0].lower()))
    return [name for name, _ in ordered[:3]]


def _fallback_mentor_reply(message: str, context: Dict[str, Any]) -> str:
    profile = context.get("profile") or {}
    tasks = context.get("recent_tasks") or []
    progress = context.get("recent_progress") or []
    syllabus = context.get("syllabus") or {}
    msg = (message or "").strip()
    lowered = msg.lower()
    tokens = set(_clean_message_tokens(message))

    pending = [t for t in tasks if str(t.get("status", "")).lower() == "pending"]
    done = [t for t in tasks if str(t.get("status", "")).lower() == "done"]
    top_pending = [str(t.get("title", "")).strip() for t in pending if str(t.get("title", "")).strip()][:3]
    recent_topics = _topic_focus_lines(progress)
    structured = syllabus.get("structured_notes") if isinstance(syllabus, dict) else []

    if isinstance(structured, list) and structured:
        lines: List[str] = [
            "1) Syllabus point coverage",
        ]
        for section in structured[:4]:
            if not isinstance(section, dict):
                continue
            title = str(section.get("title", "")).strip() or "Syllabus topic"
            summary = str(section.get("summary", "")).strip() or "Understand the core idea and its application."
            lines.append(f"- {title}: {summary}")
            key_points = section.get("keyPoints", [])
            if isinstance(key_points, list):
                for kp in key_points[:3]:
                    text = str(kp).strip()
                    if text:
                        lines.append(f"  Key point: {text}")
        lines.extend([
            "",
            "2) Action steps",
            "- Pick one syllabus point and write a 5-line explanation from memory.",
            "- Solve one related example/problem.",
            "- Review mistakes and rewrite the weak step.",
            "",
            "3) One small next move",
            "- Start with the first syllabus point above for 20 minutes now."
        ])
        return "\n".join(lines)

    if any(word in tokens for word in {"hello", "hi", "hey"}):
        return (
            "Hi. I can help with study plans, concept explanations, revision strategy, productivity, "
            "or motivation. Ask me any question and I will answer with practical steps."
        )

    if any(word in lowered for word in ("motivat", "tired", "burnout", "exhaust", "lazy", "stuck")):
        focus = top_pending[0] if top_pending else "one 10-minute study task"
        return (
            f"You do not need to solve the whole day right now. Start with {focus}, work for 10 minutes only, "
            "and aim for one visible result. After that, either continue for one more block or switch to a light "
            "revision round. Momentum matters more than intensity when motivation is low."
        )

    if any(word in lowered for word in ("plan", "schedule", "timetable", "today", "what should i do", "routine", "roadmap")):
        lines: List[str] = []
        if top_pending:
            lines.append("Start with: " + top_pending[0] + ".")
        if len(top_pending) > 1:
            lines.append("Then move to: " + top_pending[1] + ".")
        if recent_topics:
            lines.append("Close with a short recall round on " + ", ".join(recent_topics[:2]) + ".")
        energy = str(profile.get("energy", "balanced")).strip() or "balanced"
        lines.append("Use three blocks: deep work, practice, and revision.")
        lines.append(f"Keep the hardest work in your {energy} energy window and take a 10-minute break after each focused block.")
        return " ".join(lines)

    if any(word in lowered for word in ("progress", "improv", "weak", "review", "revise")):
        if recent_topics:
            return (
                "Your recent study history suggests these topics deserve review: "
                + ", ".join(recent_topics)
                + ". Pick one topic, solve one example from memory, then write a 3-line recap without notes."
            )
        return "Pick one weak topic, do one worked example, then explain it back in your own words in 3 lines."

    if any(word in lowered for word in ("task", "assignment", "problem", "homework", "project")):
        focus = top_pending[0] if top_pending else "the next pending item"
        return (
            f"Break {focus} into three parts: understand the goal, finish one small executable step, then verify the result. "
            "If it still feels big, reduce the first step until it can be done in 10-15 minutes."
        )

    if any(word in lowered for word in ("how", "what", "why", "when", "where", "which", "explain", "?")):
        context_bits: List[str] = []
        if top_pending:
            context_bits.append(f"You also have pending work like {top_pending[0]}.")
        if recent_topics:
            context_bits.append("Recent focus areas include " + ", ".join(recent_topics[:2]) + ".")
        context_hint = " ".join(context_bits)
        return (
            "Here is a practical way to approach that question: first define the core idea in one sentence, "
            "then connect it to an example, and finally test yourself by explaining it without notes. "
            + context_hint
            + " If you want, ask the same question with the exact topic name and I will turn it into exam-ready notes."
        ).strip()

    summary_bits: List[str] = []
    if top_pending:
        summary_bits.append("Your current pending work includes " + ", ".join(top_pending[:2]) + ".")
    if done:
        summary_bits.append(f"You have already completed {len(done)} recent task(s), so momentum is there.")
    if recent_topics:
        summary_bits.append("Recent focus areas: " + ", ".join(recent_topics[:2]) + ".")
    summary_bits.append(
        "Ask me for a concept explanation, a study plan, revision notes, or motivation, and I will answer directly."
    )
    return " ".join(summary_bits)


def _load_latest_syllabus_context() -> Dict[str, Any]:
    try:
        backend_module = sys.modules.get("backend")
        if backend_module is None:
            import backend as backend_module  # type: ignore

        context = getattr(backend_module, "latest_analysis_context", {}) if backend_module else {}
        if isinstance(context, dict):
            return context
    except Exception:
        pass
    return {}


@router.post("/tasks/generate-daily")
def generate_daily_tasks(user: Dict[str, Any] = Depends(get_user_from_token)):
    uid = user["id"]
    today = _today_iso(user["profile"].get("timezone", "UTC"))

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT status FROM tasks
            WHERE user_id = ? AND due_date = ?
            """,
            (uid, today),
        )
        rows = cur.fetchall()
        done = sum(1 for r in rows if r["status"] == "done")
        total = len(rows) or 1
        yesterday_completion = done / total

        cur.execute(
            """
            SELECT track, topic FROM progress_events
            WHERE user_id = ? AND created_at > ?
            ORDER BY id DESC LIMIT 8
            """,
            (uid, (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()),
        )
        weak_topics = [r["topic"] or r["track"] for r in cur.fetchall() if (r["topic"] or r["track"])]

        streak = _compute_streak(cur, uid)

    suggestions = suggest_daily_tasks(user["profile"], weak_topics, streak, yesterday_completion)
    llm_lines = _llm_complete(
        "You are a concise student productivity coach. Return 4 bullet tasks only, max 12 words each.",
        f"Student goals: {user['profile'].get('goals')}. Weak areas: {weak_topics}. "
        f"Streak={streak}. Suggested skeleton: {suggestions}. Rewrite bullets to be motivating.",
    )

    created = []
    with get_connection() as conn:
        cur = conn.cursor()
        for item in suggestions:
            title = item["title"]
            if llm_lines:
                title = item["title"]
            cur.execute(
                """
                INSERT INTO tasks (user_id, task_type, title, difficulty, status, due_date, notes, problem_statement, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    uid,
                    item["type"],
                    title,
                    int(item.get("difficulty", 2)),
                    "pending",
                    today,
                    item.get("nudge", ""),
                    (item.get("problem_statement") or "").strip(),
                    _utc_now(),
                    _utc_now(),
                ),
            )
            tid = cur.lastrowid
            created.append({"id": tid, **item, "due_date": today, "status": "pending"})

    return {"status": "ok", "tasks": created, "mentor_hint": llm_lines or "Tasks ready—start with the smallest one."}


@router.get("/tasks")
def list_tasks(date_str: Optional[str] = None, user: Dict[str, Any] = Depends(get_user_from_token)):
    target = date_str or _today_iso(user["profile"].get("timezone", "UTC"))
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, task_type, title, difficulty, status, due_date, notes, problem_statement, created_at, updated_at, completed_at
            FROM tasks WHERE user_id = ? AND due_date = ? ORDER BY id ASC
            """,
            (user["id"], target),
        )
        tasks = [row_to_dict(r) for r in cur.fetchall()]
    return {"status": "ok", "tasks": tasks, "date": target}


@router.patch("/tasks/{task_id}")
def patch_task(task_id: int, payload: TaskPatch, user: Dict[str, Any] = Depends(get_user_from_token)):
    status = payload.status.strip().lower()
    if status not in {"pending", "done", "skipped"}:
        raise HTTPException(status_code=400, detail="Invalid status")

    completed_at = _utc_now() if status == "done" else None
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE tasks SET status = ?, updated_at = ?, completed_at = ? WHERE id = ? AND user_id = ?",
            (status, _utc_now(), completed_at, task_id, user["id"]),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "ok"}


@router.post("/tasks/manual")
def manual_task(payload: TaskCreate, user: Dict[str, Any] = Depends(get_user_from_token)):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO tasks (user_id, task_type, title, difficulty, status, due_date, notes, problem_statement, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                user["id"],
                payload.task_type,
                payload.title,
                payload.difficulty,
                "pending",
                payload.due_date,
                payload.notes,
                (payload.problem_statement or "").strip(),
                _utc_now(),
                _utc_now(),
            ),
        )
        tid = cur.lastrowid
    return {"status": "ok", "id": tid}


@router.post("/progress/log")
def log_progress(payload: ProgressLog, user: Dict[str, Any] = Depends(get_user_from_token)):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO progress_events (user_id, track, delta, topic, created_at)
            VALUES (?,?,?,?,?)
            """,
            (user["id"], payload.track, float(payload.delta), payload.topic, _utc_now()),
        )
    return {"status": "ok"}


@router.get("/analytics")
def analytics(user: Dict[str, Any] = Depends(get_user_from_token)):
    uid = user["id"]
    since = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT track, SUM(delta) as total FROM progress_events WHERE user_id = ? AND created_at > ? GROUP BY track",
            (uid, since),
        )
        by_track = {row["track"]: row["total"] for row in cur.fetchall()}

        cur.execute(
            """
            SELECT due_date,
                   SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as done_count,
                   COUNT(*) as c
            FROM tasks
            WHERE user_id = ? AND due_date > date('now', '-9 day')
            GROUP BY due_date
            ORDER BY due_date ASC
            """,
            (uid,),
        )
        daily = [row_to_dict(r) for r in cur.fetchall()]

        streak = _compute_streak(cur, uid)

    weak = sorted(by_track.items(), key=lambda kv: kv[1])[:2]
    weak_labels = [k for k, _ in weak] or ["DSA", "SQL"]

    return {
        "status": "ok",
        "tracks": by_track,
        "daily_task_stats": daily,
        "streak": streak,
        "weak_areas": weak_labels,
    }


def _compute_streak(cur, user_id: int) -> int:
    cur.execute(
        "SELECT DISTINCT due_date FROM tasks WHERE user_id = ? AND status = 'done' ORDER BY due_date DESC",
        (user_id,),
    )
    completed_days = set()
    for row in cur.fetchall():
        try:
            completed_days.add(date.fromisoformat(row["due_date"]))
        except Exception:
            continue
    if not completed_days:
        return 0

    today = datetime.now(timezone.utc).date()
    anchor = today
    if anchor not in completed_days and (anchor - timedelta(days=1)) in completed_days:
        anchor = anchor - timedelta(days=1)
    elif anchor not in completed_days:
        return 0

    streak = 0
    cursor = anchor
    while cursor in completed_days:
        streak += 1
        cursor = cursor - timedelta(days=1)
    return streak


@router.get("/discipline/today")
def discipline_today(user: Dict[str, Any] = Depends(get_user_from_token)):
    uid = user["id"]
    today = _today_iso(user["profile"].get("timezone", "UTC"))
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) as c FROM tasks WHERE user_id = ? AND due_date = ?",
            (uid, today),
        )
        total = cur.fetchone()["c"] or 1
        cur.execute(
            "SELECT COUNT(*) as c FROM tasks WHERE user_id = ? AND due_date = ? AND status = 'done'",
            (uid, today),
        )
        done = cur.fetchone()["c"]
        cur.execute(
            "SELECT SUM(minutes) as m FROM focus_sessions WHERE user_id = ? AND created_at LIKE ?",
            (uid, f"{today}%"),
        )
        focus_minutes = int(cur.fetchone()["m"] or 0)
        streak = _compute_streak(cur, uid)

    score, breakdown, hint = compute_discipline_score(done / total, focus_minutes, streak)

    with get_connection() as conn:
        conn.cursor().execute(
            """
            INSERT INTO daily_scores (user_id, day, score, breakdown_json, percentile_hint)
            VALUES (?,?,?,?,?)
            ON CONFLICT(user_id, day) DO UPDATE SET
                score=excluded.score,
                breakdown_json=excluded.breakdown_json,
                percentile_hint=excluded.percentile_hint
            """,
            (uid, today, score, json.dumps(breakdown), hint),
        )

    return {
        "status": "ok",
        "day": today,
        "score": score,
        "breakdown": breakdown,
        "percentile_hint": hint,
        "streak": streak,
    }


@router.post("/recovery/evaluate")
def recovery_evaluate(user: Dict[str, Any] = Depends(get_user_from_token)):
    uid = user["id"]
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*) as c FROM tasks
            WHERE user_id = ? AND due_date > date('now', '-3 day') AND status = 'skipped'
            """,
            (uid,),
        )
        skipped = cur.fetchone()["c"]
        cur.execute(
            "SELECT COUNT(*) as c FROM tasks WHERE user_id = ? AND due_date > date('now', '-3 day')",
            (uid,),
        )
        total = max(1, cur.fetchone()["c"])
        skipped_ratio = skipped / total

        cur.execute(
            """
            SELECT due_date FROM tasks
            WHERE user_id = ? AND due_date > date('now', '-3 day')
            GROUP BY due_date
            HAVING SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) = 0
            """,
            (uid,),
        )
        missed_days = len(cur.fetchall())

    plan = recovery_plan(skipped_ratio, missed_days)
    with get_connection() as conn:
        conn.cursor().execute(
            "INSERT INTO recovery_plans (user_id, payload_json, created_at) VALUES (?,?,?)",
            (uid, json.dumps(plan), _utc_now()),
        )
    return {"status": "ok", "recovery": plan, "signals": {"skipped_ratio": round(skipped_ratio, 3), "missed_days": missed_days}}


@router.get("/shadow-mode")
def shadow_mode(user: Dict[str, Any] = Depends(get_user_from_token)):
    uid = user["id"]
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT score FROM daily_scores WHERE user_id = ? ORDER BY day DESC LIMIT 14",
            (uid,),
        )
        scores = [int(r["score"]) for r in cur.fetchall()]
    return {"status": "ok", "projection": shadow_projection(scores)}


@router.post("/focus/session")
def focus_session(payload: FocusSessionCreate, user: Dict[str, Any] = Depends(get_user_from_token)):
    focus_score = min(100, int(payload.minutes * 1.15))
    with get_connection() as conn:
        conn.cursor().execute(
            """
            INSERT INTO focus_sessions (user_id, task_id, minutes, focus_score, created_at)
            VALUES (?,?,?,?,?)
            """,
            (user["id"], payload.task_id, payload.minutes, focus_score, _utc_now()),
        )
    return {"status": "ok", "focus_score": focus_score}


@router.post("/mentor/chat")
def mentor_chat(payload: MentorChatRequest, authorization: Optional[str] = Header(default=None)):
    user: Optional[Dict[str, Any]] = None
    if authorization:
        try:
            user = get_user_from_token(authorization)
        except HTTPException:
            user = None

    progress_rows: List[Dict[str, Any]] = []
    task_rows: List[Dict[str, Any]] = []
    profile: Dict[str, Any] = default_profile()

    if user:
        uid = user["id"]
        profile = user["profile"]
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT track, delta, topic, created_at FROM progress_events WHERE user_id = ? ORDER BY id DESC LIMIT 6",
                (uid,),
            )
            progress_rows = [row_to_dict(r) for r in cur.fetchall()]
            cur.execute(
                "SELECT title, status, due_date FROM tasks WHERE user_id = ? ORDER BY id DESC LIMIT 6",
                (uid,),
            )
            task_rows = [row_to_dict(r) for r in cur.fetchall()]

    syllabus_ctx = _load_latest_syllabus_context()
    structured_notes = syllabus_ctx.get("structured_notes", []) if isinstance(syllabus_ctx, dict) else []
    topics = syllabus_ctx.get("topics", []) if isinstance(syllabus_ctx, dict) else []
    topic_lines = []
    if isinstance(topics, list):
        for topic in topics[:18]:
            if isinstance(topic, dict):
                name = str(topic.get("name", "")).strip()
                desc = str(topic.get("description", "")).strip()
                if name:
                    topic_lines.append(f"- {name}: {desc}")
    syllabus_points = []
    if isinstance(structured_notes, list):
        for section in structured_notes[:10]:
            if not isinstance(section, dict):
                continue
            title = str(section.get("title", "")).strip() or "Untitled topic"
            keys = section.get("keyPoints", [])
            if isinstance(keys, list) and keys:
                for key in keys[:4]:
                    key_text = str(key).strip()
                    if key_text:
                        syllabus_points.append(f"{title} -> {key_text}")
            else:
                summary = str(section.get("summary", "")).strip()
                if summary:
                    syllabus_points.append(f"{title} -> {summary}")

    context = {
        "profile": profile,
        "recent_progress": progress_rows,
        "recent_tasks": task_rows,
        "guest_mode": not bool(user),
        "syllabus": {
            "notes": str(syllabus_ctx.get("notes", ""))[:4000],
            "topics": topics if isinstance(topics, list) else [],
            "structured_notes": structured_notes if isinstance(structured_notes, list) else [],
        },
    }
    has_syllabus_context = bool(syllabus_points or topic_lines)
    if has_syllabus_context:
        mentor_prompt = (
            "Context JSON:\n"
            f"{json.dumps(context)[:6000]}\n\n"
            "Syllabus topics:\n"
            f"{chr(10).join(topic_lines)[:2500]}\n\n"
            "Syllabus points:\n"
            f"{chr(10).join('- ' + p for p in syllabus_points[:30])}\n\n"
            "Student message:\n"
            f"{payload.message}\n\n"
            "Reply in this exact structure:\n"
            "1) Syllabus point coverage\n"
            "2) Detailed notes\n"
            "3) Action steps\n"
            "4) One small next move\n\n"
            "Rules:\n"
            "- Answer using syllabus points, not generic text.\n"
            "- For each relevant point explain concept, importance, and one example.\n"
            "- Keep it detailed and exam-ready.\n"
            "- If the user is in guest mode, still answer fully without asking them to log in."
        )
    else:
        mentor_prompt = (
            "Context JSON:\n"
            f"{json.dumps(context)[:6000]}\n\n"
            "Student message:\n"
            f"{payload.message}\n\n"
            "Reply in this structure:\n"
            "1) Direct answer\n"
            "2) Action steps\n"
            "3) One small next move"
        )

    answer = _llm_complete(
        (
            "You are AI Student OS mentor. Answer every student message helpfully. "
            "Be clear, supportive, and actionable. Use student context when relevant, "
            "but still answer general study questions even if context is limited. "
            "Do not hallucinate scores, analytics, or completed work."
        ),
        mentor_prompt,
    )
    if not answer:
        answer = _fallback_mentor_reply(payload.message, context)
    return {"status": "ok", "answer": answer, "guest_mode": not bool(user)}


@router.post("/nudge/heartbeat")
def nudge_heartbeat(payload: NudgePing, user: Dict[str, Any] = Depends(get_user_from_token)):
    return {"status": "ok", **anti_procrastination_prompt(payload.idle_minutes)}


@router.get("/burnout/status")
def burnout_status(user: Dict[str, Any] = Depends(get_user_from_token)):
    uid = user["id"]
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*) as c FROM tasks
            WHERE user_id = ? AND due_date > date('now', '-2 day') AND status = 'skipped'
            """,
            (uid,),
        )
        skipped = cur.fetchone()["c"]
        goals = user["profile"].get("goals") or {}
        planned_hours = (
            float(goals.get("dsa", 0))
            + float(goals.get("oop", 0))
            + float(goals.get("sql", 0))
            + float(goals.get("java", 0))
            + float(goals.get("webdev", 0))
        )
    return {"status": "ok", **detect_burnout(skipped, planned_hours), "skipped_recent": skipped}
