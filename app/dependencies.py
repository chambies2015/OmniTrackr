"""
Dependencies for the OmniTrackr API.
Contains database session and authentication dependencies.
"""
import asyncio
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from . import auth, crud, models
from .database import SessionLocal, engine

# OAuth2 scheme for token-based authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


# Background tasks (emails, warm-ups, traffic counts) open their own sessions, so
# requests leave a few pooled connections for them.
BACKGROUND_CONNECTIONS = 3


def _session_slots() -> int:
    configured = os.getenv("DB_SESSION_SLOTS", "").strip()
    if configured.isdigit() and int(configured) > 0:
        return int(configured)
    pool = engine.pool
    try:
        capacity = pool.size() + max(pool._max_overflow, 0)
    except (AttributeError, TypeError):
        return 12  # Pools without a fixed size (SQLite in tests).
    return max(1, capacity - BACKGROUND_CONNECTIONS)


SESSION_SLOTS = _session_slots()
_gates: dict = {}


def _gate() -> asyncio.Semaphore:
    """One semaphore per event loop (tests run several loops)."""
    loop = asyncio.get_running_loop()
    gate = _gates.get(loop)
    if gate is None:
        gate = _gates[loop] = asyncio.Semaphore(SESSION_SLOTS)
    return gate


async def get_db():
    """Database dependency that provides a database session.

    At most SESSION_SLOTS requests hold a session at once; the rest wait here, on the
    event loop, without holding a thread or a connection. Before this, a busy moment
    (one dashboard opens dozens of requests together) could check out every pooled
    connection while all the worker threads waited for one, and the server hung
    until the pool timed out.
    """
    async with _gate():
        db = SessionLocal()
        try:
            yield db
        finally:
            await run_in_threadpool(db.close)


@asynccontextmanager
async def session_scope(provider=None):
    """A request-style session outside FastAPI's dependency system (sync or async provider)."""
    provider = provider or get_db
    generator = provider()
    if hasattr(generator, "__anext__"):
        db = await generator.__anext__()
        try:
            yield db
        finally:
            await generator.aclose()
    else:
        db = next(generator)
        try:
            yield db
        finally:
            generator.close()


# Plain (sync) functions on purpose: FastAPI runs them in its threadpool. As async
# functions they looked up the member on the event loop, and when every pooled
# database connection was busy the whole server stopped while it waited for one.
# Routes that use the database are plain functions for the same reason.
def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> models.User:
    """Dependency to get the current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token_value = token or request.cookies.get(auth.AUTH_COOKIE_NAME)
    if not token_value:
        raise credentials_exception
    
    payload = auth.decode_access_token(token_value)
    if payload is None:
        raise credentials_exception
    
    user_id = payload.get("uid")
    username: str = payload.get("sub")
    if isinstance(user_id, int) and not isinstance(user_id, bool):
        # Current tokens: the account id survives username changes.
        user = crud.get_user_by_id_auth(db, user_id)
    elif username is not None:
        # Tokens issued before ids were added (24-hour tokens, gone a day after deploy).
        user = crud.get_user_by_username_auth(db, username=username)
    else:
        raise credentials_exception
    if user is None or not user.is_active:
        raise credentials_exception
    fingerprint = payload.get("pv")
    if fingerprint is not None and fingerprint != auth.password_fingerprint(user.hashed_password):
        raise credentials_exception  # Password changed since this session began.

    return user



def get_optional_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[models.User]:
    """Resolve a viewer for privacy-aware public resources without requiring login."""
    if not token and not request.cookies.get(auth.AUTH_COOKIE_NAME):
        return None
    try:
        return get_current_user(request, token, db)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return None
        raise
