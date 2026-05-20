"""
Dependencies for the OmniTrackr API.
Contains database session and authentication dependencies.
"""
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from . import auth, crud, models
from .database import SessionLocal

# OAuth2 scheme for token-based authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


def get_db():
    """Database dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(
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
    
    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception
    
    user = crud.get_user_by_username_auth(db, username=username)
    if user is None or not user.is_active:
        raise credentials_exception
    
    return user

