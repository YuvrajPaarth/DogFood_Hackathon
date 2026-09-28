"""
auth.py — JWT authentication helpers
Handles password hashing, token creation, and current-user extraction.
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from models import User, get_db

# ── Config ───────────────────────────────────────────────────────────────────
# CHANGE THIS secret before deploying anywhere public!
SECRET_KEY  = "dogfood-hackathon-super-secret-key-change-me"
ALGORITHM   = "HS256"
TOKEN_EXPIRE_HOURS = 24   # token valid for 24 hours

# ── Passlib context for bcrypt hashing ───────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── OAuth2 scheme — reads the Bearer token from Authorization header ─────────
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ── Password helpers ─────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Turn a plain-text password into a bcrypt hash."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if the plain password matches the stored hash."""
    return pwd_context.verify(plain, hashed)


# ── JWT helpers ───────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a signed JWT token.
    data should contain at least {"sub": user_email}.
    """
    payload = data.copy()
    expire  = datetime.utcnow() + (expires_delta or timedelta(hours=TOKEN_EXPIRE_HOURS))
    payload["exp"] = expire
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Decode and verify a JWT token.
    Raises HTTPException 401 if invalid or expired.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── FastAPI dependency: get the logged-in user ────────────────────────────────

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency injected into protected routes.
    Reads the Bearer token, decodes it, and returns the User object.
    """
    payload = decode_token(token)
    email: str = payload.get("sub")

    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject"
        )

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )
    return user


# ── Role-based access helpers ─────────────────────────────────────────────────

def require_role(*roles: str):
    """
    Returns a FastAPI dependency that only allows users with one of the given roles.

    Usage:
        @router.post("/admin-only")
        def admin_route(user: User = Depends(require_role("admin"))):
            ...
    """
    def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role(s): {', '.join(roles)}"
            )
        return current_user
    return checker


# ── Convenience role dependencies ────────────────────────────────────────────
# Use these directly in route definitions:
#   def my_route(user = Depends(require_organizer)):
require_admin     = require_role("admin")
require_organizer = require_role("organizer", "admin")
require_judge     = require_role("judge", "admin")
require_participant = require_role("participant", "organizer", "admin")
