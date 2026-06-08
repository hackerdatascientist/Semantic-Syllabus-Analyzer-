# Project Module Documentation

## Overview
This document describes the key modules used in the project, including frontend files, backend files, and supporting packages. It is written so you can explain the project structure and module responsibilities to an external teacher.

---

## 1. Backend Modules

### `requirements.txt`
Contains the Python dependencies required by the backend.
- `fastapi` — the web application framework used to build API endpoints.
- `uvicorn` — ASGI server that runs the FastAPI app.
- `pydantic` — request and response validation using data models.
- `PyPDF2` — reads and extracts text content from uploaded PDF files.
- `httpx` — asynchronous HTTP client for external API requests.
- `python-multipart` — supports file upload forms in FastAPI.

### `backend.py`
This is the main server file for syllabus analysis and student management support.

Key responsibilities:
- Serve the frontend page at `/`.
- Accept syllabus uploads and text input at `/analyze`.
- Parse uploaded PDF syllabi using `PyPDF2`.
- Extract syllabus headings and topics using regex patterns.
- Return structured note summaries, topic chips, DPP questions, and exam insight data.
- Save analysis results via `/save`.
- Provide simple authentication and session handling for a student manager experience.

Key Python modules used inside `backend.py`:
- `fastapi` and `FastAPI`
- `UploadFile`, `File`, `Form`, `HTTPException`, `Depends`, `Header`
- `fastapi.responses.FileResponse`
- `fastapi.middleware.cors.CORSMiddleware`
- `pydantic.BaseModel`
- `uvicorn`
- `PyPDF2`
- `json`, `os`, `uuid`, `re`, `random`, `io`, `datetime`, `time`
- `typing.List`, `typing.Optional`, `typing.Dict`

### `student_os_api.py`
This module implements a separate Student OS API router.

Key responsibilities:
- User signup and login.
- Token-based authentication using `Authorization: Bearer ...` headers.
- Timetable generation and retrieval.
- Task creation, status updates, and progress logging.
- Mentor-style recommendations and analytics.

Key modules used:
- `fastapi.APIRouter`, `Depends`, `Header`, `HTTPException`, `Body`
- `pydantic.BaseModel`, `Field`
- `sqlite3`
- `hashlib`, `secrets`
- `datetime`, `timezone`
- `json`
- Local imports from `student_os_db.py` and `student_os_engine.py`

### `student_os_db.py`
This module manages persistence for the Student OS using SQLite.

Key responsibilities:
- Initialize the database schema in `ai_student_os.db`.
- Provide safe database connections and transaction handling.
- Store users, sessions, tasks, progress events, timetables, and recovery plans.
- Handle JSON fields and profile merging.

Key modules used:
- `sqlite3`
- `threading`
- `contextlib.contextmanager`
- `pathlib.Path`
- `datetime`, `timezone`
- `json`
- `typing`

### `student_os_engine.py`
This module contains scheduling, scoring, and recommendation logic for the Student OS.

Key responsibilities:
- Generate weekly timetables based on user profile and energy preferences.
- Insert study slots, breaks, and revision sessions.
- Compute topic mix and daily study allocation.
- Suggest tasks, recovery plans, and productivity support.

Key modules used:
- `math`
- `random`
- `datetime`
- `typing`

### `main2.py`
This file defines an independent FastAPI app for a honeytoken tracking demo.

Key responsibilities:
- Provide a token tracking endpoint at `/track/{token_id}`.
- Collect client IP and user agent data.
- Perform async external location lookup with `httpx`.
- Print alert information for a honeytoken event.

Key modules used:
- `fastapi`
- `httpx`
- `datetime`
- `uvicorn`

---

## 2. Frontend Modules

### `frontend.html`
This is the primary user interface for the project.
It contains HTML layout, inline CSS styling, and embedded JavaScript logic.

Key frontend features:
- File upload controls for syllabus PDF and book file.
- Textarea input for pasted syllabus text.
- Buttons to run analysis and refresh DPP questions.
- Notes Studio and DPP result tabs.
- A Student Manager dashboard section powered by internal API calls.
- A Three.js particle background animation.

External scripts loaded:
- `https://js.puter.com/v2/` — third-party JavaScript utility library loaded by the page.
- `https://cdnjs.cloudflare.com/ajax/libs/three.js/r134/three.min.js` — 3D rendering library used to create animated background effects.

Frontend logic in `frontend.html`:
- Detects local file or web origin and sets `APP_API_BASE`.
- Sends form data to backend `POST /analyze` and `POST /save`.
- Parses JSON responses and renders notes, topic chips, and practice questions.
- Manages Student OS UI state, auth tokens, and localStorage caching.
- Implements browser notification support for task timers.

### `script.js`
A smaller helper script in the project.

Key responsibilities:
- Collect syllabus and book file uploads.
- Send a `POST` request to `http://127.0.0.1:8000/analyze`.
- Display returned JSON results in text form.
- Toggle between human view and semantic view.

### `style.css`
A stylesheet file present in the repo, but it is not actively referenced by `frontend.html`.
The page uses inline styles instead.

---

## 3. How the App Works Together

### Frontend to Backend Flow
- The browser page loads `frontend.html`.
- The user uploads a syllabus PDF or pastes text.
- JavaScript builds `FormData` and sends it to `backend.py` at `/analyze`.
- `backend.py` extracts text, identifies syllabus topics, and builds a structured JSON response.
- The frontend renders that response into readable notes and practice problems.

### Student OS Flow
- The Student Manager section sends requests to `/api/os/...`.
- `student_os_api.py` handles auth, timetable, task updates, and user profile actions.
- `student_os_db.py` persists data in SQLite.
- `student_os_engine.py` generates schedules and scoring recommendations.

---

## 4. Teaching Tips

When explaining this project to a teacher:
1. Start with the two main parts:
   - `frontend.html` for the UI and browser interaction.
   - `backend.py` plus the Student OS modules for server logic.
2. Mention `PyPDF2` as the library responsible for reading PDF content.
3. Mention `FastAPI` as the web framework that exposes the API endpoints.
4. Describe the Student OS as a separate module group that uses SQLite and scheduling logic.
5. Point out that `three.js` is used only for visual background animation, not for core syllabus processing.

---

## 5. Recommended Talking Points

- **Backend:** `FastAPI`, `Pydantic`, `PyPDF2`, `uvicorn`, `json`, `sqlite3`, `httpx`.
- **Frontend:** HTML + CSS + JavaScript, browser `fetch()`, file uploads, localStorage, `three.js`.
- **Persistence:** `data.json` for the simple analysis state and `ai_student_os.db` for Student OS storage.
- **User-facing features:** syllabus analysis, generated notes, DPP questions, timetable and task manager.

---

## 6. Files to Show Your Teacher

- `proj_env/frontend.html`
- `proj_env/backend.py`
- `proj_env/student_os_api.py`
- `proj_env/student_os_db.py`
- `proj_env/student_os_engine.py`
- `proj_env/requirements.txt`
- `proj_env/MODULES_DOCUMENTATION.md`
