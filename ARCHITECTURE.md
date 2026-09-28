# ARCHITECTURE.md

## Overview

The platform is a single-service FastAPI backend with a SQLite database and a minimal HTML/JS frontend. It runs entirely on localhost with no external dependencies.

```
DogFood_Hackathon/
├── backend/
│   ├── main.py        — FastAPI app, all routes
│   ├── models.py      — SQLAlchemy ORM tables
│   ├── auth.py        — JWT helpers, role guards
│   ├── seed.py        — Load fixtures.json, create seed users
│   └── requirements.txt
├── frontend/
│   └── index.html     — Minimal UI
├── fixtures.json      — Fixture event data
├── docker-compose.yml
└── .dogfood.toml      — Checker config
```

## Design Decisions

### SQLite over PostgreSQL
SQLite runs with zero setup, no server process, and satisfies the "works offline" requirement. The file is persisted via a Docker volume mount. For an event with hundreds of projects and dozens of judges it is more than sufficient.

### JWT Tokens, No Session Store
JWTs are stateless — no Redis or session table needed. The token payload includes the user's email and role, so every request is self-contained. Tokens are verified on every protected route without a DB lookup.

### Role Isolation at the API Layer
Role checks live in FastAPI dependencies (`require_role()`), not in templates or the frontend. The judge score endpoint checks `current_user.role` and `current_user.id` before returning any data. A curl request with the wrong role gets a 403 before any DB query runs.

### Seeding Strategy
`seed.py` runs at startup via FastAPI's `lifespan` hook. It is idempotent — checks for the organizer seed user before inserting. It prints four `Authorization: Bearer <token>` lines to stdout so they can be pasted into `.dogfood.toml`.

### Score Normalization
Z-score normalization is applied per judge: `(raw - judge_mean) / judge_std`. Scores are then rescaled back to the 0-10 range. This corrects for judges who systematically score high or low. The method is documented in `JUDGING.md`.

## Request Flow

```
HTTP Request
    → CORS middleware
    → FastAPI route
    → OAuth2PasswordBearer reads Authorization header
    → get_current_user() decodes JWT → returns User ORM object
    → require_role() checks user.role (raises 403 if wrong)
    → Route handler runs DB query
    → Pydantic serializes response
```

## Data Flow on Startup

```
docker compose up
    → Python process starts
    → create_tables() → SQLite file created
    → run_seed() reads fixtures.json
    → Creates users, event, tracks, teams, submissions, scores
    → Prints 4 auth headers to stdout
    → Uvicorn begins accepting requests
```
