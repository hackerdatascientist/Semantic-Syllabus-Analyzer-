"""
Advanced Features Module
Includes: Enhanced burnout detection, intelligent DPP, spaced repetition,
adaptive difficulty, topic dependency graph, learning styles, exam simulation,
and progress visualization.
"""

from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Tuple
import math
import random
import json


# ============================================================================
# FEATURE 1: ENHANCED BURNOUT DETECTION
# ============================================================================

def analyze_burnout_comprehensive(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Advanced burnout detection using 6+ metrics instead of basic thresholds.
    
    Metrics:
    - Completion rate trend (last 7 days)
    - Sleep pattern consistency
    - Break frequency vs recommended
    - Task difficulty escalation
    - Mood/motivation score
    - Procrastination incidents
    """
    completion_rate = user_data.get("completion_rate", 0.5)
    avg_sleep_hours = user_data.get("avg_sleep_hours", 7)
    breaks_taken = user_data.get("breaks_taken_today", 3)
    procrastination_incidents = user_data.get("procrastination_incidents", 0)
    task_difficulty_trend = user_data.get("task_difficulty_trend", [])
    mood_score = user_data.get("mood_score", 5)  # 0-10
    
    # Calculate individual risk scores (0-1)
    completion_risk = max(0, (0.7 - completion_rate) / 0.7)  # Below 70% = risk
    sleep_risk = 1 - (min(abs(avg_sleep_hours - 7.5), 3) / 3)  # 7.5h is ideal
    break_risk = 1 - (min(breaks_taken, 8) / 8)  # At least 8 breaks in 14h day
    procrastination_risk = min(procrastination_incidents / 3, 1.0)  # 3+ = full risk
    mood_risk = 1 - (mood_score / 10)  # Lower mood = higher risk
    
    # Calculate difficulty escalation risk
    difficulty_risk = 0
    if task_difficulty_trend and len(task_difficulty_trend) >= 3:
        recent_diffs = task_difficulty_trend[-7:]
        if all(d > recent_diffs[0] for d in recent_diffs):
            difficulty_risk = 0.8
    
    # Weighted burnout index (0-100)
    weights = {
        "completion": 0.25,
        "sleep": 0.20,
        "breaks": 0.15,
        "procrastination": 0.20,
        "mood": 0.10,
        "difficulty_escalation": 0.10,
    }
    
    burnout_index = (
        completion_risk * weights["completion"] +
        sleep_risk * weights["sleep"] +
        break_risk * weights["breaks"] +
        procrastination_risk * weights["procrastination"] +
        mood_risk * weights["mood"] +
        difficulty_risk * weights["difficulty_escalation"]
    ) * 100
    
    burnout_index = max(0, min(100, burnout_index))
    
    # Risk level classification
    if burnout_index >= 75:
        risk_level = "CRITICAL"
        intervention = "Immediate: Reduce load by 50%, take 2-day rest"
    elif burnout_index >= 60:
        risk_level = "HIGH"
        intervention = "Reduce load by 30%, add 2 recovery days"
    elif burnout_index >= 40:
        risk_level = "MODERATE"
        intervention = "Monitor closely, reduce load by 10%, add breaks"
    else:
        risk_level = "LOW"
        intervention = "Maintain current pace, continue monitoring"
    
    return {
        "burnout_index": round(burnout_index, 1),
        "risk_level": risk_level,
        "intervention": intervention,
        "metric_breakdown": {
            "completion_risk": round(completion_risk, 2),
            "sleep_risk": round(sleep_risk, 2),
            "break_risk": round(break_risk, 2),
            "procrastination_risk": round(procrastination_risk, 2),
            "mood_risk": round(mood_risk, 2),
            "difficulty_escalation_risk": round(difficulty_risk, 2),
        },
        "recommendations": [
            "Prioritize sleep: aim for 7-8 hours" if sleep_risk > 0.5 else "",
            "Take more breaks: one every 50-60 minutes" if break_risk > 0.5 else "",
            "Reduce task difficulty temporarily" if difficulty_risk > 0.5 else "",
            "Talk to mentor about workload" if mood_risk > 0.7 else "",
        ]
    }


# ============================================================================
# FEATURE 2: INTELLIGENT DPP QUESTION GENERATION
# ============================================================================

def generate_intelligent_dpp(
    topics: List[str],
    user_performance: Dict[str, float],
    difficulty_level: int = 2
) -> List[Dict[str, Any]]:
    """
    Generate contextual DPP questions based on:
    - Actual syllabus topics
    - Student's past performance on similar topics
    - Adaptive difficulty
    - Question variety (MCQ, coding, theory)
    """
    if not topics:
        return []
    
    question_bank = {
        "understanding": [
            "Explain the key concept of {topic} in 2-3 sentences.",
            "How does {topic} differ from similar concepts?",
            "What are the three core principles of {topic}?",
            "Why is {topic} important in real-world applications?"
        ],
        "application": [
            "Design a solution using {topic} for this scenario: {scenario}",
            "Write pseudocode implementing {topic}",
            "How would you optimize {topic} for large datasets?",
            "Identify the {topic} pattern in this code snippet."
        ],
        "analysis": [
            "What is the time complexity of {topic} algorithm?",
            "What are edge cases for {topic}?",
            "Compare {topic} vs {alternative_topic}",
            "What trade-offs exist in {topic} implementation?"
        ],
        "tricky": [
            "What's a common mistake when using {topic}?",
            "Which scenario would {topic} fail?",
            "What hidden assumptions does {topic} make?",
            "How would you debug {topic} in production?"
        ]
    }
    
    dpp_questions = []
    weak_topics = [t for t, perf in user_performance.items() if perf < 0.6]
    
    # Generate questions biased toward weak areas
    question_types = ["understanding", "application", "analysis"]
    if weak_topics:
        question_types.extend(["tricky"])
    
    for idx, topic in enumerate(topics[:8]):
        q_type = question_types[idx % len(question_types)]
        templates = question_bank.get(q_type, question_bank["understanding"])
        template = random.choice(templates)
        
        performance = user_performance.get(topic, 0.5)
        adjusted_difficulty = difficulty_level + (1 if performance < 0.5 else -1)
        adjusted_difficulty = max(1, min(3, adjusted_difficulty))
        
        question = template.replace("{topic}", topic)
        question = question.replace("{scenario}", f"a {topic.lower()} problem")
        question = question.replace("{alternative_topic}", random.choice([t for t in topics if t != topic]))
        
        dpp_questions.append({
            "id": f"dpp_{idx}_{int(datetime.now().timestamp())}",
            "type": q_type,
            "topic": topic,
            "difficulty": adjusted_difficulty,
            "question": question,
            "performance_bias": performance,
            "recommended_time": 15 + (adjusted_difficulty * 5),
            "tags": [q_type, topic, f"difficulty-{adjusted_difficulty}"]
        })
    
    return dpp_questions


# ============================================================================
# FEATURE 3: SPACED REPETITION SYSTEM (SRS)
# ============================================================================

def calculate_review_schedule(
    topic: str,
    mastery_level: float,
    last_reviewed: date = None,
    current_date: date = None
) -> Dict[str, Any]:
    """
    Implement SM-2 algorithm (Spaced Repetition Scheduling).
    Calculates optimal review intervals based on forgetting curve.
    
    Forgetting curve: Ebbinghaus showed review intervals should be:
    1st review: 1 day
    2nd review: 3 days
    3rd review: 7 days
    4th review: 14 days
    5th review: 30 days
    """
    if current_date is None:
        current_date = date.today()
    if last_reviewed is None:
        last_reviewed = current_date
    
    days_since_review = (current_date - last_reviewed).days
    
    # Base intervals (in days)
    base_intervals = [1, 3, 7, 14, 30, 60, 120]
    
    # Adjust intervals based on mastery level
    quality_factor = mastery_level  # 0-1
    
    if quality_factor >= 0.9:
        interval_index = 0
        multiplier = 2.5
    elif quality_factor >= 0.7:
        interval_index = 0
        multiplier = 2.0
    elif quality_factor >= 0.5:
        interval_index = -1
        multiplier = 1.5
    else:
        interval_index = -2
        multiplier = 1.0
    
    interval_index = max(0, interval_index)
    
    next_interval = int(base_intervals[min(interval_index, len(base_intervals) - 1)] * multiplier)
    next_review_date = current_date + timedelta(days=next_interval)
    
    # Calculate urgency (0-1, where 1 = review immediately)
    if days_since_review >= next_interval:
        urgency = min(1.0, (days_since_review - next_interval) / 7)
    else:
        urgency = 0.0
    
    return {
        "topic": topic,
        "mastery_level": round(mastery_level, 2),
        "last_reviewed": last_reviewed.isoformat(),
        "next_review_date": next_review_date.isoformat(),
        "days_until_review": max(0, (next_review_date - current_date).days),
        "review_interval_days": next_interval,
        "urgency": round(urgency, 2),
        "review_count": interval_index + 1,
        "is_due": urgency > 0.0
    }


def get_topics_due_for_review(
    user_topics: Dict[str, Dict[str, Any]],
    current_date: date = None
) -> List[Dict[str, Any]]:
    """
    Get all topics ready for spaced repetition review.
    Sorted by urgency.
    """
    if current_date is None:
        current_date = date.today()
    
    due_topics = []
    
    for topic, data in user_topics.items():
        schedule = calculate_review_schedule(
            topic,
            data.get("mastery_level", 0.5),
            datetime.fromisoformat(data.get("last_reviewed", current_date.isoformat())).date(),
            current_date
        )
        
        if schedule["is_due"]:
            due_topics.append(schedule)
    
    return sorted(due_topics, key=lambda x: x["urgency"], reverse=True)


# ============================================================================
# FEATURE 4: ADAPTIVE DIFFICULTY CALIBRATION
# ============================================================================

def calibrate_adaptive_difficulty(
    problem_history: List[Dict[str, Any]],
    target_success_rate: float = 0.75
) -> Dict[str, Any]:
    """
    Adjust problem difficulty based on student performance.
    Target: 75% success rate (challenging but solvable).
    
    Inputs from problem_history:
    - Problem difficulty (1-3)
    - Whether student solved it
    - Time taken vs average
    - Hint usage
    """
    if not problem_history:
        return {"recommended_difficulty": 2, "confidence": 0.0}
    
    recent = problem_history[-10:]  # Last 10 problems
    
    success_count = sum(1 for p in recent if p.get("solved", False))
    success_rate = success_count / len(recent)
    
    avg_time_ratio = sum(p.get("time_taken", 15) / p.get("avg_time", 15) for p in recent) / len(recent)
    avg_hint_usage = sum(p.get("hints_used", 0) for p in recent) / len(recent)
    
    current_difficulty = recent[-1].get("difficulty", 2) if recent else 2
    
    # Adjust based on performance
    if success_rate >= target_success_rate:
        if avg_time_ratio < 0.9:  # Solving faster than average
            new_difficulty = min(3, current_difficulty + 1)
        else:
            new_difficulty = current_difficulty
    elif success_rate >= 0.5:
        new_difficulty = current_difficulty
    else:
        new_difficulty = max(1, current_difficulty - 1)
    
    confidence = min(1.0, len(recent) / 10.0)
    
    return {
        "recommended_difficulty": new_difficulty,
        "current_success_rate": round(success_rate, 2),
        "target_success_rate": target_success_rate,
        "recent_trend": "improving" if recent[-1].get("solved") else "struggling",
        "adjustment": new_difficulty - current_difficulty,
        "confidence": round(confidence, 2),
        "reasoning": f"Success rate {success_rate:.0%} vs target {target_success_rate:.0%}"
    }


# ============================================================================
# FEATURE 5: TOPIC DEPENDENCY GRAPH
# ============================================================================

def build_topic_dependency_graph(topics: List[str]) -> Dict[str, Any]:
    """
    Build a dependency graph showing prerequisite relationships.
    Example: "Sorting" depends on "Arrays", "Comparator Logic"
    """
    
    # Domain knowledge base for common dependencies
    dependency_map = {
        "Arrays": [],
        "Sorting": ["Arrays"],
        "Searching": ["Arrays"],
        "Linked Lists": [],
        "Stacks": ["Linked Lists"],
        "Queues": ["Linked Lists"],
        "Trees": [],
        "BST": ["Trees", "Sorting"],
        "Graphs": ["Trees"],
        "DFS": ["Graphs", "Stacks"],
        "BFS": ["Graphs", "Queues"],
        "Dijkstra": ["Graphs", "Priority Queue"],
        "Hash Tables": ["Arrays"],
        "Dynamic Programming": ["Recursion", "Arrays"],
        "Recursion": [],
        "Greedy": [],
        "Backtracking": ["Recursion"],
        "OOP": [],
        "Classes": ["OOP"],
        "Inheritance": ["Classes"],
        "Polymorphism": ["Inheritance"],
        "SQL": [],
        "Joins": ["SQL"],
        "Subqueries": ["SQL"],
        "Normalization": ["Databases", "SQL"],
    }
    
    graph = {}
    adjacency = {}
    
    for topic in topics:
        prerequisites = dependency_map.get(topic, [])
        graph[topic] = {
            "prerequisites": [p for p in prerequisites if p in topics],
            "dependents": []
        }
        
        if topic not in adjacency:
            adjacency[topic] = {"in": [], "out": []}
    
    # Build reverse edges
    for topic, data in graph.items():
        for prereq in data["prerequisites"]:
            if prereq in graph:
                graph[prereq]["dependents"].append(topic)
    
    # Calculate learning path (topological sort)
    learning_path = _topological_sort(graph)
    
    # Calculate complexity levels
    levels = _calculate_learning_levels(graph)
    
    return {
        "graph": graph,
        "learning_path": learning_path,
        "complexity_levels": levels,
        "ready_to_learn": _get_ready_topics(graph),
        "blocked_topics": _get_blocked_topics(graph)
    }


def _topological_sort(graph: Dict[str, Dict]) -> List[str]:
    """Topological sort to determine learning order."""
    in_degree = {node: len(graph[node]["prerequisites"]) for node in graph}
    queue = [node for node in graph if in_degree[node] == 0]
    result = []
    
    while queue:
        node = queue.pop(0)
        result.append(node)
        for dependent in graph[node]["dependents"]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)
    
    return result


def _calculate_learning_levels(graph: Dict[str, Dict]) -> Dict[str, int]:
    """Assign difficulty levels based on dependency depth."""
    levels = {}
    
    def dfs(node, depth=0):
        if node in levels:
            return max(levels[node], depth)
        levels[node] = depth
        for prereq in graph[node]["prerequisites"]:
            dfs(prereq, depth + 1)
        return levels[node]
    
    for node in graph:
        dfs(node)
    
    return levels


def _get_ready_topics(graph: Dict[str, Dict]) -> List[str]:
    """Topics student can learn right now (no prerequisites)."""
    return [topic for topic, data in graph.items() if not data["prerequisites"]]


def _get_blocked_topics(graph: Dict[str, Dict]) -> List[str]:
    """Topics blocked due to missing prerequisites."""
    return [topic for topic, data in graph.items() if data["prerequisites"]]


# ============================================================================
# FEATURE 6: LEARNING STYLE DETECTION & ADAPTATION
# ============================================================================

def detect_learning_style(interaction_history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Detect student's learning style based on interaction patterns.
    Styles: Visual, Auditory, Reading/Writing, Kinesthetic
    """
    if not interaction_history:
        return {"style": "balanced", "confidence": 0.0, "distribution": {}}
    
    recent = interaction_history[-50:]
    
    style_scores = {"visual": 0, "auditory": 0, "reading": 0, "kinesthetic": 0}
    
    for interaction in recent:
        interaction_type = interaction.get("type", "")
        
        if interaction_type in ["diagram_view", "chart_view", "image_view"]:
            style_scores["visual"] += 2
        elif interaction_type in ["video_watch", "audio_listen", "mentor_chat"]:
            style_scores["auditory"] += 2
        elif interaction_type in ["notes_read", "article_read", "text_view"]:
            style_scores["reading"] += 2
        elif interaction_type in ["problem_solve", "coding_practice", "hands_on"]:
            style_scores["kinesthetic"] += 3
        elif interaction_type in ["quick_reference"]:
            style_scores["visual"] += 1
            style_scores["reading"] += 1
    
    total = sum(style_scores.values())
    if total == 0:
        return {"style": "balanced", "confidence": 0.0, "distribution": {}}
    
    distribution = {k: round(v / total, 2) for k, v in style_scores.items()}
    primary_style = max(distribution, key=distribution.get)
    confidence = min(1.0, distribution[primary_style] - 0.25)
    
    return {
        "primary_style": primary_style,
        "secondary_style": sorted(distribution.items(), key=lambda x: x[1], reverse=True)[1][0],
        "confidence": round(confidence, 2),
        "distribution": distribution,
        "recommendations": _get_content_recommendations(primary_style)
    }


def _get_content_recommendations(style: str) -> List[str]:
    """Get content delivery recommendations based on learning style."""
    recommendations = {
        "visual": [
            "Use flowcharts and diagrams for complex topics",
            "Watch video tutorials",
            "Study concept maps and mind maps",
            "Use color-coded notes"
        ],
        "auditory": [
            "Listen to podcast explanations",
            "Discuss topics with peers",
            "Record voice explanations",
            "Attend live mentor sessions"
        ],
        "reading": [
            "Read detailed notes and textbooks",
            "Create comprehensive written notes",
            "Read code comments and documentation",
            "Solve problems with written solutions"
        ],
        "kinesthetic": [
            "Solve practice problems immediately",
            "Build projects from scratch",
            "Debug code hands-on",
            "Participate in coding marathons"
        ]
    }
    return recommendations.get(style, [])


def generate_adaptive_content(
    topic: str,
    learning_style: str,
    difficulty: int
) -> Dict[str, Any]:
    """Generate content in the appropriate format for student's learning style."""
    
    content_templates = {
        "visual": {
            "format": "diagram",
            "content": f"📊 Flowchart showing {topic} process",
            "resources": ["Diagram", "Concept Map", "Infographic"]
        },
        "auditory": {
            "format": "audio",
            "content": f"🎙️ Audio explanation of {topic}",
            "resources": ["Podcast", "Video Lecture", "Voice Notes"]
        },
        "reading": {
            "format": "text",
            "content": f"📖 Detailed written notes on {topic}",
            "resources": ["Article", "Textbook Chapter", "Documentation"]
        },
        "kinesthetic": {
            "format": "interactive",
            "content": f"🎯 Hands-on problem: Implement {topic}",
            "resources": ["Coding Challenge", "Project", "Simulation"]
        }
    }
    
    template = content_templates.get(learning_style, content_templates["reading"])
    
    return {
        "topic": topic,
        "learning_style": learning_style,
        "format": template["format"],
        "content": template["content"],
        "difficulty": difficulty,
        "estimated_time_minutes": 20 + (difficulty * 10),
        "recommended_resources": template["resources"]
    }


# ============================================================================
# FEATURE 7: EXAM SIMULATION ENGINE
# ============================================================================

def generate_exam_simulation(
    topics: List[str],
    duration_minutes: int = 120,
    num_questions: int = 50,
    difficulty_distribution: Dict[str, float] = None
) -> Dict[str, Any]:
    """
    Generate a realistic exam simulation with:
    - Realistic question distribution by topic
    - Difficulty spread
    - Time pressure
    - Realistic scoring
    """
    if difficulty_distribution is None:
        difficulty_distribution = {"easy": 0.3, "medium": 0.5, "hard": 0.2}
    
    questions = []
    total_allocated_time = 0
    
    for idx in range(num_questions):
        topic = topics[idx % len(topics)]
        
        # Distribute difficulty
        rand = random.random()
        if rand < difficulty_distribution.get("easy", 0.3):
            difficulty = 1
            time_allocated = 2
        elif rand < difficulty_distribution.get("easy", 0.3) + difficulty_distribution.get("medium", 0.5):
            difficulty = 2
            time_allocated = 4
        else:
            difficulty = 3
            time_allocated = 6
        
        total_allocated_time += time_allocated
        
        questions.append({
            "id": f"q_{idx + 1}",
            "topic": topic,
            "difficulty": difficulty,
            "time_allocated_minutes": time_allocated,
            "type": random.choice(["mcq", "short_answer", "coding"]),
            "marks": [1, 2, 3][difficulty - 1]
        })
    
    return {
        "exam_id": f"exam_{int(datetime.now().timestamp())}",
        "created_at": datetime.now().isoformat(),
        "total_questions": num_questions,
        "total_duration_minutes": duration_minutes,
        "total_marks": sum(q["marks"] for q in questions),
        "time_allocated_vs_available": round(total_allocated_time / duration_minutes, 2),
        "difficulty_distribution": difficulty_distribution,
        "questions": questions[:num_questions],
        "instructions": [
            "Manage your time carefully",
            "Attempt all questions",
            "Review your answers before submission"
        ]
    }


def evaluate_exam_performance(
    exam_data: Dict[str, Any],
    answers: List[Dict[str, Any]],
    time_taken_per_q: List[int]
) -> Dict[str, Any]:
    """
    Evaluate exam performance and predict actual exam score.
    """
    total_marks = exam_data["total_marks"]
    obtained_marks = sum(a.get("marks_obtained", 0) for a in answers)
    score_percentage = (obtained_marks / total_marks * 100) if total_marks > 0 else 0
    
    # Calculate accuracy metrics
    correct_count = sum(1 for a in answers if a.get("correct", False))
    accuracy = correct_count / len(answers) if answers else 0
    
    # Analyze timing
    total_time_taken = sum(time_taken_per_q)
    time_efficiency = exam_data["total_duration_minutes"] / total_time_taken if total_time_taken > 0 else 1
    
    # Topic-wise analysis
    topic_performance = {}
    for q in exam_data["questions"]:
        topic = q["topic"]
        matching_answer = next((a for a in answers if a.get("q_id") == q["id"]), None)
        if matching_answer:
            if topic not in topic_performance:
                topic_performance[topic] = {"correct": 0, "total": 0}
            topic_performance[topic]["total"] += 1
            if matching_answer.get("correct"):
                topic_performance[topic]["correct"] += 1
    
    topic_analysis = {
        topic: round(perf["correct"] / perf["total"], 2)
        for topic, perf in topic_performance.items()
    }
    
    weak_topics = [t for t, acc in topic_analysis.items() if acc < 0.6]
    
    # Predict actual exam performance (add 5-15% variation)
    prediction_variance = random.uniform(0.95, 1.05)
    predicted_score = min(100, score_percentage * prediction_variance)
    
    return {
        "exam_id": exam_data["exam_id"],
        "obtained_marks": obtained_marks,
        "total_marks": total_marks,
        "score_percentage": round(score_percentage, 1),
        "accuracy": round(accuracy, 2),
        "time_efficiency": round(time_efficiency, 2),
        "time_management_feedback": "Excellent pacing" if time_efficiency > 1 else "Tight on time" if time_efficiency > 0.8 else "Time pressure affected performance",
        "topic_analysis": topic_analysis,
        "weak_topics": weak_topics,
        "strong_topics": [t for t, acc in topic_analysis.items() if acc >= 0.8],
        "predicted_actual_exam_score": round(predicted_score, 1),
        "percentile_rank": _estimate_percentile(score_percentage),
        "detailed_recommendations": _generate_exam_feedback(weak_topics, topic_analysis)
    }


def _estimate_percentile(score: float) -> str:
    """Estimate percentile based on score."""
    if score >= 90:
        return "top 5% (excellent)"
    elif score >= 80:
        return "top 15% (very good)"
    elif score >= 70:
        return "top 35% (good)"
    elif score >= 60:
        return "top 55% (average)"
    else:
        return "below average"


def _generate_exam_feedback(weak_topics: List[str], topic_analysis: Dict[str, float]) -> List[str]:
    """Generate specific feedback based on exam performance."""
    feedback = []
    
    if not weak_topics:
        feedback.append("✅ Strong performance across all topics!")
    else:
        feedback.append(f"⚠️ Focus on these weak areas: {', '.join(weak_topics)}")
    
    for topic in weak_topics:
        accuracy = topic_analysis.get(topic, 0)
        if accuracy < 0.3:
            feedback.append(f"- {topic}: Review fundamentals and do basic practice")
        elif accuracy < 0.6:
            feedback.append(f"- {topic}: Solve intermediate level problems")
    
    return feedback


# ============================================================================
# FEATURE 8: PROGRESS VISUALIZATION DATA
# ============================================================================

def generate_progress_charts(user_analytics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate data for progress visualization charts:
    - Learning curve (cumulative topics mastered)
    - Discipline trend (last 30 days)
    - Topic mastery heatmap
    - Time series for each subject
    """
    
    return {
        "learning_curve": {
            "label": "Cumulative Topics Mastered",
            "data": user_analytics.get("learning_curve", []),
            "type": "line",
            "metrics": {"current": user_analytics.get("topics_mastered", 0)}
        },
        "discipline_trend": {
            "label": "30-Day Discipline Score Trend",
            "data": user_analytics.get("discipline_scores_30d", []),
            "type": "line",
            "metrics": {"average": user_analytics.get("avg_discipline_30d", 0)}
        },
        "topic_mastery": {
            "label": "Topic Mastery Levels",
            "data": user_analytics.get("topic_mastery_data", []),
            "type": "heatmap",
            "metrics": {"topics": len(user_analytics.get("topic_mastery_data", []))}
        },
        "subject_breakdown": {
            "label": "Time Spent Per Subject",
            "data": user_analytics.get("subject_hours", {}),
            "type": "pie",
            "metrics": {"total_hours": sum(user_analytics.get("subject_hours", {}).values())}
        },
        "completion_rate": {
            "label": "Task Completion Rate",
            "data": user_analytics.get("completion_trend", []),
            "type": "bar",
            "metrics": {"current_rate": user_analytics.get("current_completion_rate", 0.5)}
        }
    }
