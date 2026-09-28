"""
models.py — Database tables for the DogFood Hackathon Platform
All tables live in a local SQLite file (hackathon.db).
No external database needed.
"""

from sqlalchemy import (
    create_engine, Column, Integer, String, Text,
    Boolean, DateTime, ForeignKey, Float, Enum
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime
import enum

# ── Database setup ──────────────────────────────────────────────────────────
import os
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./hackathon.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ── Enums ───────────────────────────────────────────────────────────────────
class UserRole(str, enum.Enum):
    participant = "participant"
    judge       = "judge"
    organizer   = "organizer"
    admin       = "admin"


class SubmissionStatus(str, enum.Enum):
    draft     = "draft"
    submitted = "submitted"


# ── Tables ──────────────────────────────────────────────────────────────────

class User(Base):
    """Every person on the platform. Role controls what they can do."""
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    email         = Column(String, unique=True, index=True, nullable=False)
    username      = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role          = Column(String, default=UserRole.participant, nullable=False)
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=datetime.utcnow)

    # Relationships
    owned_teams   = relationship("Team", back_populates="owner")
    memberships   = relationship("TeamMember", back_populates="user")
    scores_given  = relationship("Score", back_populates="judge")


class Event(Base):
    """A hackathon event. Organizers create these."""
    __tablename__ = "events"

    id              = Column(Integer, primary_key=True, index=True)
    name            = Column(String, nullable=False)
    description     = Column(Text, default="")
    start_date      = Column(DateTime, nullable=False)
    end_date        = Column(DateTime, nullable=False)          # submission deadline
    is_public       = Column(Boolean, default=True)
    created_by      = Column(Integer, ForeignKey("users.id"))
    created_at      = Column(DateTime, default=datetime.utcnow)

    # Relationships
    tracks          = relationship("Track", back_populates="event", cascade="all, delete")
    prizes          = relationship("Prize", back_populates="event", cascade="all, delete")
    teams           = relationship("Team", back_populates="event")
    judge_assignments = relationship("JudgeAssignment", back_populates="event")


class Track(Base):
    """A category/track inside an event (e.g. 'AI', 'Web', 'Open')."""
    __tablename__ = "tracks"

    id          = Column(Integer, primary_key=True, index=True)
    event_id    = Column(Integer, ForeignKey("events.id"), nullable=False)
    name        = Column(String, nullable=False)
    description = Column(Text, default="")

    event       = relationship("Event", back_populates="tracks")
    submissions = relationship("Submission", back_populates="track")


class Prize(Base):
    """Prize definition for an event (e.g. '1st Place — ₹80,000')."""
    __tablename__ = "prizes"

    id          = Column(Integer, primary_key=True, index=True)
    event_id    = Column(Integer, ForeignKey("events.id"), nullable=False)
    rank        = Column(Integer, nullable=False)   # 1 = first place
    title       = Column(String, nullable=False)
    description = Column(Text, default="")
    amount      = Column(String, default="")        # stored as string e.g. "₹80,000"

    event       = relationship("Event", back_populates="prizes")


class Team(Base):
    """A team of participants. Teams submit projects."""
    __tablename__ = "teams"

    id          = Column(Integer, primary_key=True, index=True)
    event_id    = Column(Integer, ForeignKey("events.id"), nullable=False)
    owner_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    name        = Column(String, nullable=False)
    invite_code = Column(String, unique=True, index=True, nullable=False)
    created_at  = Column(DateTime, default=datetime.utcnow)

    # Relationships
    event       = relationship("Event", back_populates="teams")
    owner       = relationship("User", back_populates="owned_teams")
    members     = relationship("TeamMember", back_populates="team", cascade="all, delete")
    submission  = relationship("Submission", back_populates="team", uselist=False)


class TeamMember(Base):
    """Junction table: which users are in which teams."""
    __tablename__ = "team_members"

    id      = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)

    team    = relationship("Team", back_populates="members")
    user    = relationship("User", back_populates="memberships")


class Submission(Base):
    """A project submission by a team for an event."""
    __tablename__ = "submissions"

    id           = Column(Integer, primary_key=True, index=True)
    team_id      = Column(Integer, ForeignKey("teams.id"), nullable=False)
    track_id     = Column(Integer, ForeignKey("tracks.id"), nullable=True)
    title        = Column(String, nullable=False)
    description  = Column(Text, default="")
    repo_url     = Column(String, default="")
    demo_url     = Column(String, default="")
    video_url    = Column(String, default="")
    status       = Column(String, default=SubmissionStatus.draft)  # draft | submitted
    submitted_at = Column(DateTime, nullable=True)                  # set when status→submitted
    created_at   = Column(DateTime, default=datetime.utcnow)
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    team         = relationship("Team", back_populates="submission")
    track        = relationship("Track", back_populates="submissions")
    scores       = relationship("Score", back_populates="submission", cascade="all, delete")


class JudgeAssignment(Base):
    """Assigns a judge (user with role=judge) to an event."""
    __tablename__ = "judge_assignments"

    id         = Column(Integer, primary_key=True, index=True)
    event_id   = Column(Integer, ForeignKey("events.id"), nullable=False)
    judge_id   = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_at = Column(DateTime, default=datetime.utcnow)

    event      = relationship("Event", back_populates="judge_assignments")
    judge      = relationship("User")


class Rubric(Base):
    """
    A scoring criterion for an event (e.g. 'Innovation', weight=30%).
    Judges score each submission on each rubric criterion.
    """
    __tablename__ = "rubrics"

    id          = Column(Integer, primary_key=True, index=True)
    event_id    = Column(Integer, ForeignKey("events.id"), nullable=False)
    name        = Column(String, nullable=False)         # e.g. "Innovation"
    description = Column(Text, default="")
    max_score   = Column(Float, default=10.0)            # max points for this criterion
    weight      = Column(Float, default=1.0)             # relative weight

    scores      = relationship("Score", back_populates="rubric")


class Score(Base):
    """
    A single judge's score for one submission on one rubric criterion.
    Final score = weighted average across all rubric entries.
    """
    __tablename__ = "scores"

    id            = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"), nullable=False)
    judge_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    rubric_id     = Column(Integer, ForeignKey("rubrics.id"), nullable=False)
    score         = Column(Float, nullable=False)         # raw score (0 to rubric.max_score)
    comment       = Column(Text, default="")
    created_at    = Column(DateTime, default=datetime.utcnow)

    # Relationships
    submission    = relationship("Submission", back_populates="scores")
    judge         = relationship("User", back_populates="scores_given")
    rubric        = relationship("Rubric", back_populates="scores")


# ── Helper: create all tables ────────────────────────────────────────────────
def create_tables():
    Base.metadata.create_all(bind=engine)


# ── Dependency for FastAPI routes ────────────────────────────────────────────
def get_db():
    """Yields a database session; closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
