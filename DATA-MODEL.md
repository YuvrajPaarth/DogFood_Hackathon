# DATA-MODEL.md

## Schema

All tables are in a single SQLite file (`hackathon.db`).

### users
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| email | STRING UNIQUE | Login identifier |
| username | STRING UNIQUE | Display name |
| password_hash | STRING | bcrypt hash |
| role | STRING | participant / judge / organizer / admin |
| is_active | BOOLEAN | Default true |
| created_at | DATETIME | UTC |

### events
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| name | STRING | |
| description | TEXT | |
| start_date | DATETIME | UTC |
| end_date | DATETIME | Submission deadline (UTC) |
| is_public | BOOLEAN | Visible in gallery |
| created_by | FK → users.id | |

### tracks
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| event_id | FK → events.id | |
| name | STRING | e.g. "Developer tools" |

### prizes
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| event_id | FK → events.id | |
| rank | INTEGER | 1 = first place |
| title | STRING | e.g. "1st Place" |
| amount | STRING | e.g. "$800" |

### teams
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| event_id | FK → events.id | |
| owner_id | FK → users.id | |
| name | STRING | |
| invite_code | STRING UNIQUE | URL-safe random token |

### team_members
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| team_id | FK → teams.id | |
| user_id | FK → users.id | |
| joined_at | DATETIME | |

### submissions
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| team_id | FK → teams.id | One per team |
| track_id | FK → tracks.id | Nullable |
| title | STRING | |
| description | TEXT | |
| repo_url | STRING | |
| demo_url | STRING | |
| video_url | STRING | |
| status | STRING | draft / submitted |
| submitted_at | DATETIME | Set when status → submitted |

### rubrics
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| event_id | FK → events.id | |
| name | STRING | e.g. "functionality" |
| max_score | FLOAT | Default 10.0 |
| weight | FLOAT | Relative weight for final score |

### scores
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| submission_id | FK → submissions.id | |
| judge_id | FK → users.id | |
| rubric_id | FK → rubrics.id | |
| score | FLOAT | 0 to rubric.max_score |
| comment | TEXT | |
| created_at | DATETIME | |

### judge_assignments
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| event_id | FK → events.id | |
| judge_id | FK → users.id | |
| assigned_at | DATETIME | |

## Fixture Import

`fixtures.json` is loaded by `seed.py` at startup. The mapping:

- `fixtures.event` → one `events` row, using `submissions_close` as `end_date`
- `fixtures.tracks` → `tracks` rows linked to the event
- `fixtures.judges` → `users` rows with `role=judge` + `judge_assignments`
- `fixtures.teams` → `teams` rows, member emails create `users` if needed
- `fixtures.projects` → `submissions` rows with `status=submitted`
- `fixtures.scores` → `scores` rows, criteria keys map to `rubrics` by name

Fixture IDs (strings like `"evt_01"`) are not stored directly — they are mapped to auto-incremented integer PKs during seeding.

## Export

CSV export: `GET /api/export.csv` (organizer role required)

Columns: `submission_id, submission_title, team, track, judge_id, judge_username, rubric, rubric_weight, raw_score, weighted_score, comment`
