# DogFood Hackathon Platform

A self-hostable, open-source hackathon submission and judging platform built for the Dogfood 2026 hackathon.

## Quick Start

```bash
docker compose up
```

That's it. The platform starts on `http://localhost:8080`, seeds itself with fixture data, and prints four auth headers to stdout. Copy those into `.dogfood.toml`.

No cloud account, no hosted database, no external API, no network connection required.

## What It Does

- **T1 — Core:** JWT auth, 5 roles (visitor/participant/judge/organizer/admin), event creation with configurable dates/tracks/prizes, team formation via invite links, project submission with draft/edit until deadline, deadline enforcement, public searchable gallery.
- **T2 — Judging:** Judge invitation and assignment, weighted configurable rubrics, backend-enforced role isolation (judges cannot see peer scores at the API level), judge progress dashboard, cross-judge z-score normalization, CSV export.

## Running Locally Without Docker

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8080
```

## API

Interactive docs at `http://localhost:8080/docs`

Key endpoints:

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/gallery` | none | Public project gallery |
| POST | `/auth/register` | none | Register new user |
| POST | `/auth/login` | none | Login, returns JWT |
| POST | `/projects/new` | participant | Create submission (blocked if deadline passed) |
| GET | `/api/judge/scores` | judge | View own scores only |
| GET | `/api/judge/scores?judge=X` | organizer | View any judge's scores |
| GET | `/api/export.csv` | organizer | Download all scores as CSV |
| GET | `/api/events/{id}/results` | organizer | Rankings with normalization |

## Running the Acceptance Suite

```bash
python3 run.py .dogfood.toml > acceptance-report.txt
```

Note: JWT tokens in `.dogfood.toml` expire after 24 hours. If tests fail with 401, restart the server to get fresh tokens and update `.dogfood.toml`.

## What Is Not Yet Implemented

- T3: Community voting, comments, anti-abuse
- T4: Webhooks, certificates, embeddable widget
- Frontend is minimal (API-first, use `/docs` for full interaction)

## Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy, SQLite
- **Auth:** JWT (python-jose), bcrypt (passlib)
- **Frontend:** Plain HTML/CSS/JS
- **Container:** Docker + Docker Compose

## License

MIT — see LICENSE file.
