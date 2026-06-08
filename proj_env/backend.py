from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Header
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import uvicorn
import json
import time
import uuid
import re
import random
import io
import PyPDF2
from datetime import datetime, date
import os

app = FastAPI(title="Student Manager Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def read_index():
    return FileResponse("frontend.html")

# --- Persistence (JSON File) ---
DATA_FILE = "data.json"

def load_db():
    if not os.path.exists(DATA_FILE):
        return {"users": {}, "accounts": {}, "tasks": {}, "timetables": {}, "focus_sessions": {}, "verifications": {}, "last_analysis": {}}
    try:
        with open(DATA_FILE, "r") as f:
            db = json.load(f)
            # Ensure all keys exist
            for key in ["users", "accounts", "tasks", "timetables", "focus_sessions", "verifications", "last_analysis"]:
                if key not in db:
                    db[key] = {}
            return db
    except:
        return {"users": {}, "accounts": {}, "tasks": {}, "timetables": {}, "focus_sessions": {}, "verifications": {}, "last_analysis": {}}

def save_db(db):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(db, f, indent=4)
    except Exception as e:
        print(f"ERROR: Failed to save database: {e}")

DB = load_db()

class TaskPatch(BaseModel):
    status: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserSignup(BaseModel):
    username: str
    password: str
    display_name: str

class TimetableUpdate(BaseModel):
    days: List[dict]
    meta: Optional[dict] = None

def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split(" ")[1]
    user = DB["users"].get(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user

@app.post("/analyze")
async def analyze_syllabus(
    syllabus: Optional[UploadFile] = File(None),
    book: Optional[UploadFile] = File(None),
    syllabus_text: Optional[str] = Form(None),
    refresh: bool = False
):
    input_source = "Text Input"
    text_content = syllabus_text or ""
    
    if syllabus:
        input_source = f"File: {syllabus.filename}"
        try:
            content = await syllabus.read()
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
            extracted_text = ""
            for page in pdf_reader.pages:
                extracted_text += page.extract_text() + "\n"
            if extracted_text.strip():
                text_content = extracted_text
        except Exception as e:
            print(f"PDF Extraction Error: {e}")
    
    # Create a unique hash for this syllabus content
    content_hash = str(hash(text_content) % (2**32))
    
    # Improved division logic - try to find "Units" or "Points"
    syllabus_points = []
    if text_content:
        # Strategy 1: Look for lines that look like Unit/Chapter headers
        headers = re.findall(r'(?:Unit|Chapter|Section|Module)\s*[\dI-V]+[:.\s]+.*', text_content, re.IGNORECASE)
        if headers:
            syllabus_points = [h.strip() for h in headers[:25]]
        
        # Strategy 2: If no clear headers, look for numbered list items (e.g., 1. Introduction)
        if not syllabus_points:
            list_items = re.findall(r'(?:\d+\.|\*|\-)\s+([A-Z][A-Za-z\s]{5,50})', text_content)
            if list_items:
                syllabus_points = [li.strip() for li in list_items[:25]]
        
        # Strategy 3: Fallback to keyword phrases
        if not syllabus_points:
            potential_topics = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text_content)
            unique_topics = []
            for t in potential_topics:
                if len(t) > 5 and t not in unique_topics:
                    unique_topics.append(t)
            syllabus_points = unique_topics[:20]

    if not syllabus_points:
        syllabus_points = ["Module 1: Advanced Architecture", "Module 2: System Optimization", "Module 3: Security & Protocols"]

    dynamic_topic = syllabus_points[0] if syllabus_points else "the provided syllabus"

    # Build highly detailed structured notes for EACH POINT
    structured_notes = []
    for point in syllabus_points:
        # Extract context based on the point name
        search_term = re.sub(r'^(Unit|Chapter|Section|Module)\s*[\dI-V]+[:.\s]+', '', point, flags=re.IGNORECASE).strip()
        context_matches = re.finditer(f'[^.!?]*\\b{re.escape(search_term[:15])}\\b[^.!?]*[.!?]', text_content, re.IGNORECASE)
        sentences = [m.group(0).strip() for m in context_matches]
        
        if sentences:
            summary_text = " ".join(sentences[:6]) 
        else:
            summary_text = f"This section provides an in-depth exploration of {point}. It covers the core theoretical frameworks, practical application constraints, and the strategic importance of this topic within the broader curriculum."

        # Create a "Clear & Precise" long-form markdown response for this point
        chatgpt_style_note = f"""### 📝 Detailed Breakdown: {point}

#### 🔍 What is {search_term}?
{summary_text}

In simple terms, **{search_term}** is a core component of the syllabus that deals with the fundamental logic and structure of high-performance systems. It is the part of the program that ensures data is processed efficiently and reliably across the entire network.

#### 🎯 Why is it Important?
*   **System Stability:** Without {search_term}, complex systems would struggle to maintain consistency under heavy loads.
*   **Performance Scaling:** It provides the "blueprint" for how a program can grow from a small local script to a global distributed service.
*   **Data Integrity:** It ensures that every piece of information is accounted for and processed without errors or data loss.

#### 💡 Key Points to Remember
*   **The Core Logic:** Focus on how {search_term} manages its internal state and interacts with external modules.
*   **Optimization:** Remember that the main goal of {search_term} is to reduce latency and increase throughput.
*   **Standard Practice:** In the industry, {search_term} is implemented using well-tested patterns to ensure it can be easily maintained and updated.

#### 🎓 Exam Preparation Tip
When you are asked about **{search_term}** in an exam, start by defining its primary role in the system. Then, list at least two real-world benefits (like scalability or reliability). Clear, direct answers often score the highest marks.
"""

        structured_notes.append({
            "title": f"Module Analysis: {point}",
            "content": chatgpt_style_note
        })

    # Add a final summary section
    structured_notes.append({
        "title": "Consolidated Strategic Summary",
        "content": f"""### 🏁 Consolidated Strategic Summary

After reviewing all **{len(syllabus_points)} key points**, we have identified that the core strength of this syllabus lies in its focus on **{dynamic_topic}**. 

**Final Takeaways:**
*   **Consistency is Key:** The recurring theme across all modules is the maintenance of system-wide integrity.
*   **Optimization-First Thinking:** Every chapter pushes toward more efficient resource utilization.
*   **Future Readiness:** The curriculum prepares you for real-world scaling challenges.

**Good luck with your studies!**
"""
    })

    # Build a conversational main summary with "advanced" tone
    main_summary = f"""### Advanced Technical Analysis: {input_source}
We have completed an exhaustive semantic mapping of your syllabus. Our analysis has identified **{len(syllabus_points)} distinct syllabus points** requiring high-level focus.

The curriculum is heavily weighted towards **{dynamic_topic}**, suggesting an emphasis on system-wide optimization and theoretical mastery. Each module below has been expanded with "Deep Dive" metrics to ensure you capture the advanced nuances often tested in higher-tier examinations.
"""

# Generate NEW unique DPP questions on EVERY request (not cached)
    # Questions should be specific to the topics found in THIS syllabus
    question_templates = [
        {"text": "What is the primary architectural consideration when scaling {topic}?", "options": ["Horizontal scaling", "Vertical scaling", "Redundancy", "Latency"], "correctAnswer": "Horizontal scaling"},
        {"text": "Which pitfall is most common in {topic} implementation?", "options": ["Premature optimization", "Thorough docs", "Regular testing", "Clear requirements"], "correctAnswer": "Premature optimization"},
        {"text": "How does {topic} handle high-concurrency edge cases?", "options": ["Locking mechanisms", "Clock speed", "Manual intervention", "Service shutdown"], "correctAnswer": "Locking mechanisms"},
        {"text": "What theoretical framework describes {topic} logic?", "options": ["Systemic Modularism", "Linear Monolithism", "Random Execution", "Static Inheritance"], "correctAnswer": "Systemic Modularism"},
        {"text": "What is the most critical security risk for {topic}?", "options": ["Injection attacks", "Power usage", "Response time", "Excessive logging"], "correctAnswer": "Injection attacks"},
        {"text": "How would you optimize {topic} for performance?", "options": ["Caching", "Blocking", "Sleeping", "Waiting"], "correctAnswer": "Caching"},
        {"text": "What is the key challenge in {topic} scalability?", "options": ["Resource management", "Sleep management", "Network speed", "CPU power"], "correctAnswer": "Resource management"},
        {"text": "Which best practice applies to {topic} design?", "options": ["Modularity", "Monolithic design", "Tight coupling", "Static binding"], "correctAnswer": "Modularity"}
    ]
    
    # Shuffle and select random templates
    shuffled_templates = random.sample(question_templates, min(5, len(question_templates)))
    
    # Generate questions using ACTUAL topics from the syllabus
    dpp_questions = []
    for idx, tpl in enumerate(shuffled_templates):
        # Use topics in round-robin to ensure all topics are covered in questions
        topic = syllabus_points[idx % len(syllabus_points)]
        dpp_questions.append({
            "text": tpl["text"].format(topic=topic),
            "options": tpl["options"],
            "correctAnswer": tpl["correctAnswer"]
        })

    # Add topics for the chip cloud
    topics_list = [{"name": kw, "weight": random.choice(["High", "Medium"]), "description": f"Focus area identified from {input_source}"} for kw in syllabus_points]

    mock_data = {
        "notes": main_summary,
        "structuredNotes": structured_notes,
        "topics": topics_list,
        "topicRelationships": [
            {"from": syllabus_points[0], "to": syllabus_points[1] if len(syllabus_points)>1 else "System Core", "type": "dependency"}
        ],
        "exclusiveInsights": {
            "syllabusFingerprint": f"Balanced technical structure focusing on {dynamic_topic}.",
            "prerequisiteChain": ["Foundational Logic", f"Intro to {syllabus_points[0]}"],
            "revisionPriority": [
                {"topic": syllabus_points[0], "priority": "CRITICAL", "reason": "Highest weightage detected."}
            ]
        },
        "ambushMode": {
            "headline": "Exam Trap Prediction",
            "blindSpots": [
                {"topic": dynamic_topic, "riskLevel": "HIGH", "whyRisky": "Abstract definitions often mixed in MCQs.", "triggerSignal": "Questions starting with 'Explain the nuances of...'", "rescueMove": "Focus on the 3-pillar definition."}
            ]
        },
        "dpp": dpp_questions
    }
    return {"status": "success", "data": mock_data}

@app.post("/save")
async def save_analysis(data: dict):
    # For now, we'll just save it to data.json under a 'last_analysis' key for the global state
    # or just acknowledge it was received.
    DB["last_analysis"] = data
    save_db(DB)
    return {"status": "success", "message": "Analysis saved to database"}

@app.post("/api/os/auth/signup")
async def signup(user: UserSignup):
    if user.username in DB["accounts"]:
        raise HTTPException(status_code=400, detail="User exists")
    token = str(uuid.uuid4())
    DB["accounts"][user.username] = {"password": user.password, "display_name": user.display_name, "profile": {"energy": "morning", "exam_mode": False}}
    DB["users"][token] = user.username
    
    # Initialize tasks
    if user.username not in DB["tasks"]: 
        DB["tasks"][user.username] = []
    
    # Initialize timetable with 7 days
    days_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    tt_days = [{"name": name, "date": "", "timeline": []} for name in days_names]
    DB["timetables"][user.username] = {"days": tt_days, "meta": {"notes": ""}}
    
    save_db(DB)
    print(f"DEBUG: New user signed up: {user.username}")
    return {"token": token, "user": {"username": user.username, "display_name": user.display_name}}

@app.post("/api/os/auth/login")
async def login(user: UserLogin):
    account = DB["accounts"].get(user.username)
    if not account:
        raise HTTPException(status_code=401, detail="Account not found. Please click Sign Up first.")
    if account["password"] != user.password:
        raise HTTPException(status_code=401, detail="Incorrect password.")
    token = str(uuid.uuid4())
    DB["users"][token] = user.username
    save_db(DB)
    print(f"DEBUG: User logged in: {user.username}")
    return {"token": token, "user": {"username": user.username, "display_name": account.get("display_name", user.username)}}

@app.get("/api/os/discipline/today")
async def get_discipline(username: str = Depends(get_current_user)):
    tasks = DB["tasks"].get(username, [])
    done = len([t for t in tasks if t.get("status") == "done"])
    return {"score": 50 + (done * 10), "percentile_hint": "Progressing", "streak": 1 if done > 0 else 0}

@app.get("/api/os/timetable")
async def get_timetable(username: str = Depends(get_current_user)):
    return {"timetable": DB["timetables"].get(username, {"days": []})}

@app.put("/api/os/timetable")
async def update_timetable(tt: TimetableUpdate, username: str = Depends(get_current_user)):
    DB["timetables"][username] = tt.dict()
    save_db(DB)
    return {"status": "success"}

@app.post("/api/os/timetable/generate")
async def generate_timetable(username: str = Depends(get_current_user)):
    days_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    tt_days = []
    for name in days_names:
        tt_days.append({
            "name": name,
            "date": str(date.today()), # Simplified for now
            "timeline": []
        })
    tt = {"days": tt_days}
    DB["timetables"][username] = tt
    save_db(DB)
    return {"status": "success", "timetable": tt}

@app.get("/api/os/tasks")
async def get_tasks(username: str = Depends(get_current_user)):
    return {"tasks": DB["tasks"].get(username, [])}

@app.post("/api/os/tasks/generate-daily")
async def generate_daily_tasks(username: str = Depends(get_current_user)):
    topics = [
        "Array & Hashing", "Two Pointers", "Sliding Window", "Stack", "Binary Search",
        "Linked List", "Trees (BFS/DFS)", "Tries", "Backtracking", "Heaps / Priority Queues",
        "Graphs (Dijkstra/BFS/DFS)", "Dynamic Programming", "Bit Manipulation", "Greedy Algorithms", "Intervals"
    ]
    import random
    # Select 5 unique DSA topics
    selected = random.sample(topics, 5)
    new_tasks = []
    
    # Task type pool for DSA variety
    task_types = ["implementation", "optimization", "pattern-matching", "theory"]
    
    for i, t in enumerate(selected):
        difficulty = random.randint(2, 5)
        t_type = random.choice(task_types)
        new_tasks.append({
            "id": int(time.time() * 1000) + i,
            "title": f"DSA: {t} ({t_type.capitalize()})",
            "task_type": "coding",
            "difficulty": difficulty,
            "status": "pending",
            "problem_statement": f"Solve a {difficulty}-star challenge on {t}. Focus on time complexity (Big O) and efficient {t_type}."
        })
    
    # Overwrite with fresh 5 tasks as requested ("every time new ones")
    DB["tasks"][username] = new_tasks
    save_db(DB)
    print(f"DEBUG: Generated 5 new tasks for {username}")
    return {"status": "success", "tasks": new_tasks}

@app.patch("/api/os/tasks/{task_id}")
async def patch_task(task_id: int, patch: TaskPatch, username: str = Depends(get_current_user)):
    tasks = DB["tasks"].get(username, [])
    found_idx = -1
    for i, t in enumerate(tasks):
        if t["id"] == task_id:
            found_idx = i
            break
    
    if found_idx == -1:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks[found_idx]
    
    task["status"] = patch.status
    save_db(DB)
    
    response = {"status": "success"}
    
    if patch.status == "done":
        topic = task["title"].replace(" Masterclass", "")
        response["dpp"] = {
            "message": f"Well done on {topic}! Here are your practice problems:",
            "questions": [
                {"q": f"Explain the central theorem of {topic}.", "a": "Refer to standard proof."},
                {"q": f"Calculate the derivative/output for a {topic} system.", "a": "Result varies by input."}
            ]
        }
    
    save_db(DB)
    return response

def build_task_verification(task):
    title = task.get("title", "this task")
    # Extract topic name
    topic = title.split(":", 1)[-1].strip() if ":" in title else title
    # Remove things in parentheses (like (Implementation)) to get clean topic name
    clean_topic = re.sub(r"\([^)]*\)", "", topic).strip()
    
    # Extract sub-type from parenthesis if present
    sub_type_match = re.search(r"\(([^)]+)\)", topic)
    sub_type = sub_type_match.group(1).lower() if sub_type_match else ""
    
    # Fallback to checking the problem_statement or task_type
    problem_stmt = task.get("problem_statement", "").lower()
    task_type = task.get("task_type", "").lower()
    
    # Classify the task
    category = "general"
    if "implementation" in sub_type or "implementation" in problem_stmt:
        category = "implementation"
    elif "optimization" in sub_type or "optimize" in problem_stmt:
        category = "optimization"
    elif "pattern" in sub_type or "pattern" in problem_stmt:
        category = "pattern-matching"
    elif "theory" in sub_type or "theory" in problem_stmt or "theory" in task_type:
        category = "theory"

    templates = {
        "implementation": [
            {
                "question": f"When implementing the core algorithm for '{clean_topic}', which design step is most critical for correctness?",
                "correct": "Define clear base cases and handle empty, null, or out-of-bounds inputs first.",
                "decoys": [
                    "Maximize loop depth to ensure the algorithm exhausts all possible pathways.",
                    "Hardcode inputs from the problem description to save execution time.",
                    "Skip validation steps since compiler assertions will capture errors automatically."
                ]
            },
            {
                "question": f"When writing unit tests for your '{clean_topic}' implementation, which test cases are most essential?",
                "correct": "Edge cases like empty structures, single elements, duplicate values, and boundaries.",
                "decoys": [
                    "Only large, maximum-capacity datasets to test scaling limits.",
                    "Standard input values matching the sample outputs precisely.",
                    "Inputs consisting exclusively of positive sequential integers."
                ]
            },
            {
                "question": f"Which of the following is a classic logic bug encountered when coding '{clean_topic}'?",
                "correct": "Off-by-one index boundaries, integer overflow, or incorrect pointer reassignments.",
                "decoys": [
                    "CSS stylesheet layout conflicts on render.",
                    "Database thread deadlock due to missing connection pool size configuration.",
                    "Virtual machine memory thrashing due to garbage collector disablement."
                ]
            }
        ],
        "optimization": [
            {
                "question": f"If your initial solution for '{clean_topic}' has O(N^2) time complexity, what is the best strategy to optimize it?",
                "correct": "Introduce a hash map for O(1) lookups or leverage sorted order with two pointers.",
                "decoys": [
                    "Wrap the nested loops inside a try-catch block to bypass CPU cycle limits.",
                    "Sort the dataset multiple times at each step of the iteration.",
                    "Split the loops into multiple functions to distribute execution overhead."
                ]
            },
            {
                "question": f"What represents the primary space complexity trade-off when optimizing the runtime of '{clean_topic}'?",
                "correct": "Using auxiliary space (like stacks, queues, or maps) to store and reuse precomputed results.",
                "decoys": [
                    "Increased disk storage requirements to persist compilation outputs.",
                    "Higher network latency from transmitting larger memory dumps.",
                    "Decreased compile-time efficiency with no impact on run-time memory."
                ]
            },
            {
                "question": f"Which metric is most vital when verifying the performance optimization of '{clean_topic}'?",
                "correct": "Asymptotic time complexity (Big O) across worst-case scaling inputs.",
                "decoys": [
                    "The number of local variables initialized in the function body.",
                    "The raw line count of the source code file.",
                    "The styling parameters applied to the debugger terminal interface."
                ]
            }
        ],
        "pattern-matching": [
            {
                "question": f"What is the key indicator that a coding problem can be solved using the '{clean_topic}' pattern?",
                "correct": "The problem asks for contiguous ranges, pairs of numbers, or traversal of hierarchical nodes.",
                "decoys": [
                    "The problem specifies that the execution environment is highly parallel.",
                    "The input is guaranteed to be a stream of text from an external network connection.",
                    "The requirements focus heavily on graphical display layout and form submission."
                ]
            },
            {
                "question": f"Why is identifying the '{clean_topic}' pattern early in an interview highly beneficial?",
                "correct": "It connects the problem to a standard algorithm template with known complexity bounds.",
                "decoys": [
                    "It guarantees that the solution is automatically bug-free.",
                    "It allows you to bypass writing the actual code and jump to the design summary.",
                    "It automatically registers your code with the local test harness."
                ]
            },
            {
                "question": f"Which standard algorithm or structure is a direct application of the '{clean_topic}' pattern?",
                "correct": "Classic traversal techniques, window expansion/contraction, or stack-based backtracking.",
                "decoys": [
                    "Universal relational database indexing schemas.",
                    "RESTful API route matching algorithms.",
                    "Asymmetric public key generation methods."
                ]
            }
        ],
        "theory": [
            {
                "question": f"What is the fundamental theoretical property defining '{clean_topic}'?",
                "correct": "Structured relationships like parent-child hierarchies, strict ordering, or LIFO/FIFO constraints.",
                "decoys": [
                    "Continuous algebraic distribution under a bell curve.",
                    "State preservation across asynchronous network transport layers.",
                    "Non-deterministic execution paths governed by random seed values."
                ]
            },
            {
                "question": f"What is the theoretical worst-case lookup time complexity for an element in a balanced '{clean_topic}' structure?",
                "correct": "O(log N)",
                "decoys": [
                    "O(1)",
                    "O(N^2)",
                    "O(N log N)"
                ]
            },
            {
                "question": f"In computational complexity theory, how does '{clean_topic}' typically help manage complexity?",
                "correct": "By organizing elements to enable logarithmic search, divide-and-conquer divisions, or constant-time accesses.",
                "decoys": [
                    "By compiling dynamic inputs into machine code binary instructions.",
                    "By compressing data objects using Huffman coding algorithms.",
                    "By validating cryptographic hash signatures across nodes."
                ]
            }
        ],
        "general": [
            {
                "question": f"What is the most critical step to verify your work on '{clean_topic}' before completion?",
                "correct": "Manually run the algorithm against edge cases, empty values, and extreme bounds to ensure logic holds.",
                "decoys": [
                    "Assume that if the sample tests pass, all potential edge cases are successfully handled.",
                    "Immediately mark the task complete and proceed to the next module without review.",
                    "Disable error handling modules to improve performance under stress testing."
                ]
            },
            {
                "question": f"Which development habit is best suited for mastering '{clean_topic}' concepts?",
                "correct": "Implementing the core algorithm from memory and explaining the time/space trade-offs in your own words.",
                "decoys": [
                    "Copying a pre-written library method without examining its internal complexity.",
                    "Memorizing code syntax line-by-line without understanding the underlying logic flow.",
                    "Bypassing practice problems and focusing exclusively on theoretical descriptions."
                ]
            }
        ]
    }

    # Get templates for the detected category (fallback to general)
    category_templates = templates.get(category, templates["general"])
    
    # Select a template using task ID to keep it deterministic per task
    task_id = task.get("id", 0)
    template_idx = task_id % len(category_templates)
    selected_template = category_templates[template_idx]
    
    # Prepare option list
    correct_text = selected_template["correct"]
    decoy_texts = selected_template["decoys"]
    
    # Combine correct answer and decoys
    options_data = [{"text": correct_text, "is_correct": True}]
    for decoy in decoy_texts:
        options_data.append({"text": decoy, "is_correct": False})
        
    # Shuffle options deterministically based on task_id
    rng = random.Random(task_id)
    rng.shuffle(options_data)
    
    options = [item["text"] for item in options_data]
    correct_index = [idx for idx, item in enumerate(options_data) if item["is_correct"]][0]
    
    return {
        "question": selected_template["question"],
        "options": options,
        "correctIndex": correct_index
    }

@app.get("/api/os/tasks/{task_id}/verify")
async def get_task_verification(task_id: int, username: str = Depends(get_current_user)):
    tasks = DB["tasks"].get(username, [])
    task = next((t for t in tasks if t["id"] == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.get("status") == "done":
        raise HTTPException(status_code=400, detail="Task is already complete")

    challenge = build_task_verification(task)
    if username not in DB["verifications"]:
        DB["verifications"][username] = {}
    DB["verifications"][username][str(task_id)] = challenge
    save_db(DB)
    return {"question": challenge["question"], "options": challenge["options"]}

@app.post("/api/os/tasks/{task_id}/verify")
async def submit_task_verification(task_id: int, body: dict, username: str = Depends(get_current_user)):
    stored = DB["verifications"].get(username, {})
    challenge = stored.get(str(task_id))
    if not challenge:
        raise HTTPException(status_code=404, detail="Verification challenge not found")
    answer = body.get("answer")
    if answer is None or not isinstance(answer, int):
        raise HTTPException(status_code=400, detail="Answer index is required")
    if answer != challenge.get("correctIndex"):
        raise HTTPException(status_code=400, detail="Incorrect answer. Please review the task and try again.")

    tasks = DB["tasks"].get(username, [])
    task = next((t for t in tasks if t["id"] == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task["status"] = "done"
    save_db(DB)
    # Remove used challenge
    del DB["verifications"][username][str(task_id)]
    save_db(DB)
    return {"status": "success", "message": "Verification passed. Task marked as done."}

@app.get("/api/os/burnout/status")
async def get_burnout_status(username: str = Depends(get_current_user)):
    # Mock burnout status logic
    tasks = DB["tasks"].get(username, [])
    skipped_recent = len([t for t in tasks if t.get("status") == "skipped"])
    recommendation = "You're doing great! Keep it up." if skipped_recent < 2 else "You might need a break soon."
    return {"skipped_recent": skipped_recent, "recommendation": recommendation}

@app.post("/api/os/recovery/evaluate")
async def evaluate_recovery(username: str = Depends(get_current_user)):
    # Mock recovery evaluation
    return {
        "recovery": {
            "headline": "Optimal Recovery Path",
            "actions": ["Take a 15-min walk", "Hydrate properly", "Review your top priority task"]
        }
    }

@app.post("/api/os/nudge/heartbeat")
async def nudge_heartbeat(data: dict, username: str = Depends(get_current_user)):
    idle_minutes = data.get("idle_minutes", 0)
    if idle_minutes > 15:
        return {
            "trigger": True,
            "message": "It's been a while since your last activity.",
            "micro_task": "Try a quick 2-minute stretching session."
        }
    return {"trigger": False}

@app.post("/api/os/focus/session")
async def focus_session(data: dict, username: str = Depends(get_current_user)):
    minutes = data.get("minutes", 25)
    if username not in DB["focus_sessions"]:
        DB["focus_sessions"][username] = []
    DB["focus_sessions"][username].append({"timestamp": time.time(), "minutes": minutes})
    save_db(DB)
    return {"status": "success", "message": f"Logged {minutes} focus minutes."}

@app.put("/api/os/profile")
async def update_profile(profile: dict, username: str = Depends(get_current_user)):
    # Profile is stored inside the account
    account = DB["accounts"].get(username)
    if account:
        account["profile"] = profile
        save_db(DB)
        return {"status": "success", "profile": profile}
    raise HTTPException(status_code=404, detail="Account not found")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
