"""
seed.py — Load fixtures.json into the database and print the four auth headers.

Run once at startup (called from main.py lifespan).
Also runnable standalone: python seed.py

The checker needs these four Bearer tokens printed at startup so you can paste
them into .dogfood.toml.
"""

import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from models import (
    SessionLocal, create_tables,
    User, Event, Track, Prize, Team, TeamMember,
    Submission, JudgeAssignment, Rubric, Score,
    SubmissionStatus,
)
from auth import hash_password, create_access_token

# ── Paths ────────────────────────────────────────────────────────────────────
# fixtures.json: check env var first, then repo root (one level above backend/)
import os as _os
_env_fixtures = _os.environ.get("FIXTURES_PATH")
if _env_fixtures:
    FIXTURES_PATH = Path(_env_fixtures)
else:
    FIXTURES_PATH = Path(__file__).parent.parent / "fixtures.json"


# ── Fixed seed passwords (deterministic, printed at startup) ─────────────────
SEED_PASSWORDS = {
    "organizer": "organizer-pass-dogfood",
    "judge_a":   "judge-a-pass-dogfood",
    "judge_b":   "judge-b-pass-dogfood",
    "participant": "participant-pass-dogfood",
}


def _parse_dt(s: str | None) -> datetime | None:
    """Parse an ISO 8601 UTC string to a naive UTC datetime."""
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    return dt.replace(tzinfo=None)  # store naive UTC in SQLite


def already_seeded(db: Session) -> bool:
    return db.query(User).filter(User.email == "organizer@seed.dogfood").first() is not None


def run_seed(db: Session) -> dict:
    """
    Seed the database. Returns a dict with the four auth headers.
    Idempotent — skips if already seeded.
    """
    if already_seeded(db):
        # Return tokens for the existing seed users
        return _build_tokens(db)

    # ── Load fixtures ─────────────────────────────────────────────────────────
    fixtures = {}
    if FIXTURES_PATH.exists():
        with open(FIXTURES_PATH) as f:
            fixtures = json.load(f)
    else:
        print(f"[seed] WARNING: {FIXTURES_PATH} not found — seeding with minimal data")

    event_data    = fixtures.get("event", {})
    tracks_data   = fixtures.get("tracks", [])
    judges_data   = fixtures.get("judges", [])
    teams_data    = fixtures.get("teams", [])
    projects_data = fixtures.get("projects", [])
    scores_data   = fixtures.get("scores", [])

    # ── Create the four fixed seed users ──────────────────────────────────────
    organizer = User(
        email="organizer@seed.dogfood",
        username="organizer",
        password_hash=hash_password(SEED_PASSWORDS["organizer"]),
        role="organizer",
    )
    judge_a = User(
        email="judge_a@seed.dogfood",
        username="judge_a",
        password_hash=hash_password(SEED_PASSWORDS["judge_a"]),
        role="judge",
    )
    judge_b = User(
        email="judge_b@seed.dogfood",
        username="judge_b",
        password_hash=hash_password(SEED_PASSWORDS["judge_b"]),
        role="judge",
    )
    participant = User(
        email="participant@seed.dogfood",
        username="participant",
        password_hash=hash_password(SEED_PASSWORDS["participant"]),
        role="participant",
    )
    db.add_all([organizer, judge_a, judge_b, participant])
    db.flush()  # get IDs without committing

    # ── Create the fixture event ───────────────────────────────────────────────
    # Use the fixture's submissions_close so the deadline check passes T1.3
    sub_close_str = event_data.get("submissions_close", "2026-03-01T18:00:00Z")
    sub_close_dt  = _parse_dt(sub_close_str)

    event = Event(
        name=event_data.get("name", "Sample Hack 2026"),
        description="Fixture event loaded from fixtures.json",
        start_date=datetime(2026, 1, 1),
        end_date=sub_close_dt or datetime(2026, 3, 1, 18, 0, 0),
        is_public=True,
        created_by=organizer.id,
    )
    db.add(event)
    db.flush()

    # ── Create tracks from fixtures ───────────────────────────────────────────
    track_map: dict[str, Track] = {}  # fixture id → ORM object
    for t in tracks_data:
        track = Track(
            event_id=event.id,
            name=t.get("name", "General"),
            description="",
        )
        db.add(track)
        db.flush()
        track_map[t["id"]] = track

    # Default track if fixtures had none
    if not track_map:
        default_track = Track(event_id=event.id, name="Open", description="")
        db.add(default_track)
        db.flush()
        track_map["_default"] = default_track

    # ── Add default prizes ────────────────────────────────────────────────────
    for rank, title, amount in [
        (1, "1st Place", "$800"),
        (2, "2nd Place", "$500"),
        (3, "3rd Place", "$350"),
    ]:
        db.add(Prize(event_id=event.id, rank=rank, title=title, amount=amount))

    # ── Create default rubric criteria ───────────────────────────────────────
    rubric_map: dict[str, Rubric] = {}
    for name, weight in [("functionality", 1.5), ("quality", 1.0), ("innovation", 1.2), ("presentation", 0.8)]:
        r = Rubric(event_id=event.id, name=name, max_score=10.0, weight=weight)
        db.add(r)
        db.flush()
        rubric_map[name] = r

    # ── Create judge users from fixtures + assign to event ────────────────────
    judge_user_map: dict[str, User] = {}  # fixture judge id → User
    # Map the two seed judges to the first two fixture judge IDs
    fixture_judge_ids = [j["id"] for j in judges_data]
    seed_judge_objects = [judge_a, judge_b]

    for i, jdata in enumerate(judges_data):
        if i < len(seed_judge_objects):
            # Reuse our seed judge accounts for the first two fixture judges
            ju = seed_judge_objects[i]
        else:
            # Create extra judge users for remaining fixture judges
            ju = User(
                email=jdata.get("email", f"judge_{jdata['id']}@seed.dogfood"),
                username=f"judge_{jdata['id']}",
                password_hash=hash_password("judgepass"),
                role="judge",
            )
            db.add(ju)
            db.flush()

        judge_user_map[jdata["id"]] = ju
        db.add(JudgeAssignment(event_id=event.id, judge_id=ju.id))

    # Assign our two seed judges even if not in fixtures
    for sj in [judge_a, judge_b]:
        exists = db.query(JudgeAssignment).filter_by(event_id=event.id, judge_id=sj.id).first()
        if not exists:
            db.add(JudgeAssignment(event_id=event.id, judge_id=sj.id))

    # ── Create teams and participants from fixtures ───────────────────────────
    team_map: dict[str, Team] = {}   # fixture team id → Team
    for tdata in teams_data:
        # Owner is our seed participant (or create a new user per team)
        owner = participant
        members_emails = tdata.get("members", [])
        if members_emails:
            # Try to find or create a user for the first member
            first_email = members_emails[0]
            existing = db.query(User).filter(User.email == first_email).first()
            if not existing:
                existing = User(
                    email=first_email,
                    username=first_email.split("@")[0],
                    password_hash=hash_password("memberpass"),
                    role="participant",
                )
                db.add(existing)
                db.flush()
            owner = existing

        team = Team(
            event_id=event.id,
            owner_id=owner.id,
            name=tdata.get("name", f"Team {tdata['id']}"),
            invite_code=secrets.token_urlsafe(8),
        )
        db.add(team)
        db.flush()
        team_map[tdata["id"]] = team

        # Add owner as member
        db.add(TeamMember(team_id=team.id, user_id=owner.id))

    # ── Create a team for our seed participant if not already in a team ───────
    if participant.id not in [
        m.user_id for m in db.query(TeamMember).all()
    ]:
        seed_team = Team(
            event_id=event.id,
            owner_id=participant.id,
            name="Seed Participant Team",
            invite_code=secrets.token_urlsafe(8),
        )
        db.add(seed_team)
        db.flush()
        db.add(TeamMember(team_id=seed_team.id, user_id=participant.id))
        # Give this team a submitted project
        seed_sub = Submission(
            team_id=seed_team.id,
            track_id=list(track_map.values())[0].id,
            title="Seed Participant Project",
            description="A project seeded for testing.",
            repo_url="https://github.com/example/seed",
            status=SubmissionStatus.submitted,
            submitted_at=datetime(2026, 2, 15, 12, 0, 0),
        )
        db.add(seed_sub)

    # ── Create submissions from fixture projects ───────────────────────────────
    project_map: dict[str, Submission] = {}
    for pdata in projects_data:
        team_id_fixture = pdata.get("team")
        track_id_fixture = pdata.get("track", "_default")

        team_obj  = team_map.get(team_id_fixture)
        track_obj = track_map.get(track_id_fixture) or list(track_map.values())[0]

        if not team_obj:
            # Create a minimal team for orphaned projects
            anon_owner = User(
                email=f"auto_{pdata['id']}@seed.dogfood",
                username=f"auto_{pdata['id']}",
                password_hash=hash_password("autopass"),
                role="participant",
            )
            db.add(anon_owner)
            db.flush()
            team_obj = Team(
                event_id=event.id,
                owner_id=anon_owner.id,
                name=f"Team for {pdata['id']}",
                invite_code=secrets.token_urlsafe(8),
            )
            db.add(team_obj)
            db.flush()
            db.add(TeamMember(team_id=team_obj.id, user_id=anon_owner.id))
            team_map[team_id_fixture] = team_obj

        sub = Submission(
            team_id=team_obj.id,
            track_id=track_obj.id,
            title=pdata.get("title", f"Project {pdata['id']}"),
            description=pdata.get("summary", ""),
            repo_url=pdata.get("repo_url", ""),
            demo_url=pdata.get("demo_url", ""),
            status=SubmissionStatus.submitted,
            submitted_at=_parse_dt(pdata.get("submitted_at")),
        )
        db.add(sub)
        db.flush()
        project_map[pdata["id"]] = sub

    # ── Load scores from fixtures ─────────────────────────────────────────────
    for sdata in scores_data:
        judge_fixture_id   = sdata.get("judge")
        project_fixture_id = sdata.get("project")
        criteria           = sdata.get("criteria", {})
        comment            = sdata.get("comment", "")

        judge_user_obj = judge_user_map.get(judge_fixture_id, judge_a)
        sub_obj        = project_map.get(project_fixture_id)
        if not sub_obj:
            continue

        for criterion_name, raw_score in criteria.items():
            rubric_obj = rubric_map.get(criterion_name)
            if not rubric_obj:
                # Create rubric on the fly for unknown criteria
                rubric_obj = Rubric(
                    event_id=event.id,
                    name=criterion_name,
                    max_score=10.0,
                    weight=1.0,
                )
                db.add(rubric_obj)
                db.flush()
                rubric_map[criterion_name] = rubric_obj

            # Avoid duplicate scores (idempotency)
            existing_score = db.query(Score).filter_by(
                submission_id=sub_obj.id,
                judge_id=judge_user_obj.id,
                rubric_id=rubric_obj.id,
            ).first()
            if not existing_score:
                db.add(Score(
                    submission_id=sub_obj.id,
                    judge_id=judge_user_obj.id,
                    rubric_id=rubric_obj.id,
                    score=float(raw_score),
                    comment=comment,
                ))

    # Add sample scores from our two seed judges on fixture projects
    # so the T2 checker tests have something to read
    for proj_obj in list(project_map.values())[:5]:
        for judge_obj in [judge_a, judge_b]:
            for rname, rubric_obj in list(rubric_map.items())[:2]:
                exists = db.query(Score).filter_by(
                    submission_id=proj_obj.id,
                    judge_id=judge_obj.id,
                    rubric_id=rubric_obj.id,
                ).first()
                if not exists:
                    db.add(Score(
                        submission_id=proj_obj.id,
                        judge_id=judge_obj.id,
                        rubric_id=rubric_obj.id,
                        score=7.0,
                        comment="Seeded score.",
                    ))

    db.commit()
    print("[seed] Database seeded successfully.")
    return _build_tokens(db)


def _build_tokens(db: Session) -> dict:
    """Generate JWT tokens for the four seed users and return auth headers."""
    def get_user(email: str) -> User | None:
        return db.query(User).filter(User.email == email).first()

    users = {
        "organizer":   get_user("organizer@seed.dogfood"),
        "judge_a":     get_user("judge_a@seed.dogfood"),
        "judge_b":     get_user("judge_b@seed.dogfood"),
        "participant": get_user("participant@seed.dogfood"),
    }

    headers = {}
    for role, user in users.items():
        if user:
            token = create_access_token({"sub": user.email, "role": user.role})
            headers[role] = f"Bearer {token}"

    return headers


def print_auth_headers(headers: dict) -> None:
    """
    Print the four auth headers to stdout.
    Copy these into your .dogfood.toml [auth] section.
    """
    print("\n" + "=" * 60)
    print("DOGFOOD AUTH HEADERS — paste into .dogfood.toml")
    print("=" * 60)
    for role, header in headers.items():
        print(f'{role:<12} = "Authorization: {header}"')
    print("=" * 60 + "\n")


if __name__ == "__main__":
    create_tables()
    db = SessionLocal()
    try:
        headers = run_seed(db)
        print_auth_headers(headers)
    finally:
        db.close()
