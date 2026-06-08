# Project Entity Relationship Diagram

This visual diagram shows the main SQLite schema used by the student manager portion of the project.

```mermaid
erDiagram
    users {
        INTEGER id PK
        TEXT username UNIQUE
        TEXT password_hash
        TEXT display_name
        TEXT profile_json
        TEXT created_at
    }

    sessions {
        TEXT token PK
        INTEGER user_id FK
        TEXT created_at
        TEXT expires_at
    }

    tasks {
        INTEGER id PK
        INTEGER user_id FK
        TEXT task_type
        TEXT title
        INTEGER difficulty
        TEXT status
        TEXT due_date
        TEXT notes
        TEXT problem_statement
        TEXT created_at
        TEXT updated_at
        TEXT completed_at
    }

    progress_events {
        INTEGER id PK
        INTEGER user_id FK
        TEXT track
        REAL delta
        TEXT topic
        TEXT created_at
    }

    focus_sessions {
        INTEGER id PK
        INTEGER user_id FK
        INTEGER task_id FK
        INTEGER minutes
        INTEGER focus_score
        TEXT created_at
    }

    timetables {
        INTEGER id PK
        INTEGER user_id FK
        TEXT week_start
        TEXT payload_json
        TEXT created_at
    }

    daily_scores {
        INTEGER id PK
        INTEGER user_id FK
        TEXT day
        INTEGER score
        TEXT breakdown_json
        TEXT percentile_hint
    }

    recovery_plans {
        INTEGER id PK
        INTEGER user_id FK
        TEXT payload_json
        TEXT created_at
    }

    users ||--o{ sessions : has
    users ||--o{ tasks : owns
    users ||--o{ progress_events : logs
    users ||--o{ focus_sessions : tracks
    users ||--o{ timetables : owns
    users ||--o{ daily_scores : records
    users ||--o{ recovery_plans : creates

    tasks ||--o{ focus_sessions : referenced_by
```

## How to use
- Add this file to your project documentation.
- If your editor or docs viewer supports Mermaid, it will render the diagram visually.
- You can also copy the Mermaid block into any Markdown file or GitHub README.

## Notes
- `users` is the central entity.
- `sessions` tracks login tokens.
- `tasks` stores student tasks and can optionally be referenced by `focus_sessions`.
- `timetables`, `daily_scores`, and `recovery_plans` store structured JSON payloads tied to a user.
