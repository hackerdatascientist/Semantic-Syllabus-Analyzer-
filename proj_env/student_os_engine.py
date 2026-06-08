"""
Rule-based scheduling, discipline scoring, recovery/shadow projections for AI Student OS.
"""

from __future__ import annotations

import math
import random
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Tuple

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _parse_hhmm(value: str) -> Tuple[int, int]:
    parts = (value or "09:00").strip().split(":")
    h = int(parts[0]) if parts and parts[0].isdigit() else 9
    m = int(parts[1]) if len(parts) > 1 and str(parts[1]).isdigit() else 0
    return max(0, min(23, h)), max(0, min(59, m))


def _minutes_since_midnight(h: int, m: int) -> int:
    return h * 60 + m


def _fmt_minutes(total: int) -> str:
    total = max(0, total)
    h, m = divmod(total, 60)
    return f"{h:02d}:{m:02d}"


def _overlap(a0: int, a1: int, b0: int, b1: int) -> Tuple[int, int]:
    start = max(a0, b0)
    end = min(a1, b1)
    if end <= start:
        return start, start
    return start, end


def _subtract_busy(free_segments: List[Tuple[int, int]], busy: Tuple[int, int]) -> List[Tuple[int, int]]:
    b0, b1 = busy
    out: List[Tuple[int, int]] = []
    for s0, s1 in free_segments:
        if b1 <= s0 or b0 >= s1:
            out.append((s0, s1))
            continue
        if b0 > s0:
            out.append((s0, min(b0, s1)))
        if b1 < s1:
            out.append((max(b1, s0), s1))
    return [(x, y) for x, y in out if y - x >= 15]


def generate_weekly_timetable(profile: Dict[str, Any], week_start: date) -> Dict[str, Any]:
    """
    Build a coarse weekly grid: fixed blocks + study allocations + breaks.
    Missed-task reschedule and overload hooks are represented as meta flags for the client.
    """
    sleep = profile.get("sleep") or {}
    sleep_start = _parse_hhmm(str(sleep.get("start", "23:30")))
    sleep_end = _parse_hhmm(str(sleep.get("end", "06:30")))
    energy = str(profile.get("energy", "balanced")).lower()
    exam_mode = bool(profile.get("exam_mode"))
    goals = profile.get("goals") or {}
    dsa_h = float(goals.get("dsa", 8))
    oop_h = float(goals.get("oop", 5))
    sql_h = float(goals.get("sql", 5))
    java_h = float(goals.get("java", 6))
    webdev_h = float(goals.get("webdev", 5))
    total_weekly_target = max(8.0, dsa_h + oop_h + sql_h + java_h + webdev_h)

    if exam_mode:
        dsa_h *= 1.15
        oop_h *= 1.08
        sql_h *= 1.08
        java_h *= 1.1
        webdev_h *= 1.05

    ratio_sum = max(1.0, dsa_h + oop_h + sql_h + java_h + webdev_h)
    r_dsa = dsa_h / ratio_sum
    r_oop = oop_h / ratio_sum
    r_sql = sql_h / ratio_sum
    r_java = java_h / ratio_sum
    r_webdev = webdev_h / ratio_sum

    days_out: List[Dict[str, Any]] = []
    overload_risk = False

    for day_index in range(7):
        wake = sleep_end
        bed = sleep_start
        wake_m = _minutes_since_midnight(*wake)
        bed_m = _minutes_since_midnight(*bed)
        if bed_m <= wake_m:
            bed_m += 24 * 60

        free_segments = [(wake_m, bed_m)]

        fixed_blocks = list(profile.get("fixed_blocks") or [])
        optional_blocks = list(profile.get("optional_blocks") or [])

        busy_merged: List[Tuple[int, int, str, str]] = []

        for block in fixed_blocks:
            days = block.get("days") or []
            if day_index not in days:
                continue
            st = _parse_hhmm(str(block.get("start", "09:00")))
            en = _parse_hhmm(str(block.get("end", "10:00")))
            s = _minutes_since_midnight(*st)
            e = _minutes_since_midnight(*en)
            if e <= s:
                e += 24 * 60
            busy_merged.append((s, e, str(block.get("label", "Block")), "fixed"))

        for block in optional_blocks:
            days = block.get("days") or []
            if day_index not in days:
                continue
            st = _parse_hhmm(str(block.get("start", "09:00")))
            en = _parse_hhmm(str(block.get("end", "10:00")))
            s = _minutes_since_midnight(*st)
            e = _minutes_since_midnight(*en)
            if e <= s:
                e += 24 * 60
            busy_merged.append((s, e, str(block.get("label", "Block")), "optional"))

        busy_merged.sort(key=lambda x: x[0])
        for s, e, label, kind in busy_merged:
            free_segments = _subtract_busy(free_segments, (s, e))

        free_minutes = sum(max(0, b - a) for a, b in free_segments)
        daily_target = total_weekly_target * 60 / 7
        if free_minutes < daily_target * 0.85:
            overload_risk = True

        peak_start, peak_end = _peak_window(energy, wake_m, bed_m)

        study_slots: List[Dict[str, Any]] = []
        for seg_start, seg_end in free_segments:
            seg_len = seg_end - seg_start
            if seg_len < 25:
                continue
            chunk_target = max(25, int(min(seg_len, 55)))
            cursor = seg_start
            while cursor + 25 <= seg_end:
                end_chunk = min(cursor + chunk_target, seg_end)
                mid = (cursor + end_chunk) // 2
                in_peak = peak_start <= mid <= peak_end
                study_slots.append({
                    "start": _fmt_minutes(cursor % (24 * 60)),
                    "end": _fmt_minutes(end_chunk % (24 * 60)),
                    "label": "Deep work" if in_peak else "Study block",
                    "category": "study",
                    "intensity": "high" if in_peak else "normal",
                })
                study_slots.append({
                    "start": _fmt_minutes(end_chunk % (24 * 60)),
                    "end": _fmt_minutes(min(end_chunk + 10, seg_end) % (24 * 60)),
                    "label": "Break",
                    "category": "break",
                    "intensity": "low",
                })
                cursor = end_chunk + 10
                chunk_target = max(25, min(50, seg_end - cursor))

        revision_slot = None
        if study_slots:
            revision_slot = {
                "start": study_slots[-1]["start"],
                "end": study_slots[-1]["end"],
                "label": "Revision / recall",
                "category": "revision",
                "intensity": "medium",
            }

        fixed_rows: List[Dict[str, Any]] = []
        for s, e, lab, cat in busy_merged:
            fixed_rows.append({
                "start": _fmt_minutes(s % (24 * 60)),
                "end": _fmt_minutes(e % (24 * 60)),
                "label": lab,
                "category": "fixed" if cat == "fixed" else "optional",
                "intensity": "fixed",
            })

        merged_timeline = sorted(
            fixed_rows + study_slots,
            key=lambda item: _minutes_since_midnight(*_parse_hhmm(item["start"]))
        )

        alloc = _allocate_topics_for_day(day_index, r_dsa, r_oop, r_sql, r_java, r_webdev, len(study_slots))

        days_out.append({
            "index": day_index,
            "name": DAY_NAMES[day_index],
            "date": (week_start + timedelta(days=day_index)).isoformat(),
            "timeline": merged_timeline,
            "revision": revision_slot,
            "topic_mix": alloc,
            "free_minutes": int(free_minutes),
        })

    return {
        "week_start": week_start.isoformat(),
        "days": days_out,
        "meta": {
            "overload_risk": overload_risk,
            "exam_mode": exam_mode,
            "energy": energy,
            "notes": "Hard tasks auto-prefer peak energy window; breaks inserted every ~50 minutes.",
        },
    }


def _peak_window(energy: str, wake_m: int, bed_m: int) -> Tuple[int, int]:
    span = max(120, bed_m - wake_m)
    if energy == "morning":
        return wake_m + 30, wake_m + int(span * 0.35)
    if energy == "night":
        return bed_m - int(span * 0.35), bed_m - 30
    mid = wake_m + span // 2
    return mid - 60, mid + 60


def _allocate_topics_for_day(
    day_index: int, r_dsa: float, r_oop: float, r_sql: float, r_java: float, r_webdev: float, study_blocks: int
) -> Dict[str, float]:
    weights = {
        "DSA": r_dsa,
        "OOP": r_oop,
        "SQL": r_sql,
        "Java": r_java,
        "WebDev": r_webdev,
    }
    if day_index >= 5:
        weights["WebDev"] *= 1.05
        weights["DSA"] *= 0.95
        weights["SQL"] *= 1.02
    total = sum(weights.values()) or 1.0
    return {k: round(v / total, 3) for k, v in weights.items()}


def suggest_daily_tasks(
    profile: Dict[str, Any],
    weak_topics: List[str],
    streak: int,
    yesterday_completion: float,
) -> List[Dict[str, Any]]:
    exam_mode = bool(profile.get("exam_mode"))
    base_diff = 2 if exam_mode else 2 if yesterday_completion > 0.6 else 1

    weak = weak_topics[0] if weak_topics else "core pattern"
    goals = profile.get("goals") or {}

    track_hours = {
        "DSA": float(goals.get("dsa", 8)),
        "OOP": float(goals.get("oop", 5)),
        "SQL": float(goals.get("sql", 5)),
        "Java": float(goals.get("java", 6)),
        "WebDev": float(goals.get("webdev", 5)),
    }

    challenge_bank = {
        "DSA": [
            (
                "Solve 2 competitive DSA questions on arrays and hashing",
                "Pick two competitive programming questions on arrays or hashing. For each: identify constraints, derive the optimal approach, code it, and test with at least 3 edge cases.",
            ),
            (
                "Solve 1 timed DSA problem on trees or graphs",
                "Choose one competitive problem on trees or graphs and solve it in 35 minutes. After coding, write the key traversal or state idea in 4 lines.",
            ),
            (
                f"Attack one weak DSA pattern: {weak}",
                "Focus on one weak DSA pattern only. Solve one guided problem, then solve one new variant without notes and document the step where your logic breaks.",
            ),
        ],
        "OOP": [
            (
                "Practice 3 OOP design questions with classes and interfaces",
                "Solve three OOP-style design questions. Define classes, interfaces, and relationships, then explain why inheritance or composition is the better fit.",
            ),
            (
                "Solve 2 OOP scenario questions on abstraction and polymorphism",
                "Pick two OOP interview-style scenarios. Identify the abstractions, method contracts, and runtime behavior with one short code sketch for each.",
            ),
        ],
        "SQL": [
            (
                "Solve 3 SQL questions on joins, grouping, and filtering",
                "Choose three SQL practice problems using JOIN, GROUP BY, and WHERE or HAVING. Write each query and explain the row flow and one likely mistake.",
            ),
            (
                "Practice 2 SQL questions on subqueries and constraints",
                "Solve two SQL interview problems involving subqueries, keys, or constraints. For each one, state why your query is better than a naive approach.",
            ),
        ],
        "Java": [
            (
                "Solve 2 Java coding questions on strings and collections",
                "Pick two Java placement-style questions. Solve them using clean methods, explain the collection or API choice, and write the time complexity.",
            ),
            (
                "Practice 1 Java debugging task and 1 output-based question",
                "Take one Java debugging problem and one output prediction problem. Explain the exact language rule behind each answer, not only the result.",
            ),
        ],
        "WebDev": [
            (
                "Build 1 mini frontend challenge using HTML, CSS, and JS",
                "Complete one small frontend challenge such as a validator, interactive card, or responsive component. Focus on structure, behavior, and clean DOM updates.",
            ),
            (
                "Solve 2 webdev interview tasks on DOM and APIs",
                "Answer two web development questions involving DOM manipulation or fetch/API handling. Implement one example and explain the event and data flow.",
            ),
        ],
    }

    ordered_tracks = sorted(track_hours.items(), key=lambda item: item[1], reverse=True)
    chosen_tracks = [name for name, hours in ordered_tracks if hours > 0][:5]
    if not chosen_tracks:
        chosen_tracks = ["DSA", "OOP", "SQL", "Java", "WebDev"]

    tasks = []
    for index, track in enumerate(chosen_tracks[:5]):
        bank = challenge_bank.get(track, [])
        title, problem_statement = bank[index % len(bank)]
        diff_boost = 1 if exam_mode and track in {"DSA", "Java", "SQL"} else 0
        tasks.append({
            "type": track,
            "title": title,
            "difficulty": min(3, max(1, base_diff + diff_boost)),
            "nudge": _nudge_for_streak(streak),
            "problem_statement": problem_statement,
        })
    return tasks

def _nudge_for_streak(streak: int) -> str:
    if streak >= 7:
        return "Consistency streak is strong—keep the cadence, not the pressure."
    if streak == 0:
        return "Start with five minutes on the smallest subtask."
    return "Ship one tiny win before noon."


def compute_discipline_score(
    completion_rate: float,
    focus_minutes: int,
    streak: int,
) -> Tuple[int, Dict[str, Any], str]:
    comp = max(0.0, min(1.0, completion_rate))
    focus_ratio = max(0.0, min(1.0, focus_minutes / 120))
    streak_ratio = max(0.0, min(1.0, streak / 14))
    score = int(round(comp * 40 + focus_ratio * 35 + streak_ratio * 25))
    score = max(0, min(100, score))
    breakdown = {
        "completion": round(comp * 40, 1),
        "focus": round(focus_ratio * 35, 1),
        "consistency": round(streak_ratio * 25, 1),
    }
    percentile = _percentile_hint(score)
    return score, breakdown, percentile


def _percentile_hint(score: int) -> str:
    if score >= 88:
        return "You performed like top 10% today."
    if score >= 75:
        return "You performed like top 25% today."
    if score >= 60:
        return "Solid middle pack—small tweaks will compound."
    if score >= 40:
        return "Room to rebound tomorrow with lighter targets."
    return "Recovery mode recommended—reduce load and rebuild streak."


def recovery_plan(skipped_ratio: float, missed_days: int) -> Dict[str, Any]:
    reduce = 0.25 if skipped_ratio < 0.5 else 0.4
    days = 3 if missed_days < 2 else 4
    return {
        "headline": "Gentle recovery plan",
        "reduce_load_by": reduce,
        "horizon_days": days,
        "actions": [
            "Shrink daily task list by {}% for {} days.".format(int(reduce * 100), days),
            "Swap one hard block for review or walk.",
            "Re-anchor wake time; skip guilt—log wins only.",
        ],
        "burnout_guard": skipped_ratio > 0.55 or missed_days > 1,
    }


def shadow_projection(discipline_scores: List[int]) -> Dict[str, Any]:
    if not discipline_scores:
        base = 52
    else:
        base = sum(discipline_scores) / len(discipline_scores)
    series = []
    for d in range(0, 31):
        drift = math.sin(d / 4.2) * 4
        noise = random.uniform(-2.6, 2.6)
        val = max(0, min(100, base + drift * 0.35 + noise + d * 0.15))
        series.append({"day": d, "score": round(val, 1)})
    outlook = "Trajectory improves if completion stays above 65%." if base >= 55 else "Trajectory flattens unless missed tasks drop."
    return {"series": series, "outlook": outlook}


def detect_burnout(skipped_last_48h: int, planned_hours: float) -> Dict[str, Any]:
    risk = skipped_last_48h >= 5 or planned_hours > 12
    return {
        "burnout_risk": risk,
        "recommendation": "Add a recovery half-day and remove lowest-priority block." if risk else "Workload looks sustainable.",
    }


def anti_procrastination_prompt(idle_minutes: int) -> Dict[str, Any]:
    if idle_minutes < 25:
        return {"trigger": False, "message": ""}
    return {
        "trigger": True,
        "message": "Start with 5 minutes: open IDE and scaffold one function.",
        "micro_task": "Write problem statement in your own words (90s).",
    }
