"""
User CRUD operations for the OmniTrackr API.
"""
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session, load_only
from sqlalchemy import func, or_

from .. import models, schemas


def get_user_by_username(db: Session, username: str) -> Optional[models.User]:
    """Get user by username."""
    return db.query(models.User).filter(models.User.username == username).first()


def get_user_by_username_auth(db: Session, username: str) -> Optional[models.User]:
    """Get user by username with minimal columns for auth."""
    return db.query(models.User).options(
        load_only(
            models.User.id,
            models.User.email,
            models.User.username,
            models.User.hashed_password,
            models.User.is_active,
            models.User.is_verified,
            models.User.verification_token,
            models.User.created_at,
            models.User.profile_picture_url,
        )
    ).filter(models.User.username == username).first()


def get_user_by_id_auth(db: Session, user_id: int) -> Optional[models.User]:
    """Get user by id with minimal columns for auth (session tokens carry the id)."""
    return db.query(models.User).options(
        load_only(
            models.User.id,
            models.User.email,
            models.User.username,
            models.User.hashed_password,
            models.User.is_active,
            models.User.is_verified,
            models.User.verification_token,
            models.User.created_at,
            models.User.profile_picture_url,
        )
    ).filter(models.User.id == user_id).first()


def _unique_case_insensitive(db: Session, *conditions) -> Optional[models.User]:
    """The one member matching regardless of case; None when there is no single match."""
    matches = db.query(models.User).filter(or_(*conditions)).limit(2).all()
    return matches[0] if len(matches) == 1 else None


def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    """Get user by email (exact match first, then a unique case-insensitive one)."""
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None and email:
        user = _unique_case_insensitive(db, func.lower(models.User.email) == email.strip().lower())
    return user


def get_user_by_username_or_email(db: Session, username_or_email: str) -> Optional[models.User]:
    """Get user by username or email: an exact username, then an exact email, then a unique case-insensitive match.

    An older account's email may equal someone else's username, and an
    unordered OR match could then resolve sign-in to the wrong account.
    """
    user = (db.query(models.User).filter(models.User.username == username_or_email).first()
            or db.query(models.User).filter(models.User.email == username_or_email).order_by(models.User.id).first())
    if user is None and username_or_email:
        needle = username_or_email.strip().lower()
        user = _unique_case_insensitive(
            db, func.lower(models.User.username) == needle, func.lower(models.User.email) == needle,
        )
    return user


def get_user_by_id(db: Session, user_id: int) -> Optional[models.User]:
    """Get user by ID."""
    return db.query(models.User).filter(models.User.id == user_id).first()


def create_user(db: Session, user: schemas.UserCreate, hashed_password: str, verification_token: str = None) -> models.User:
    """Create a new user with hashed password."""
    db_user = models.User(
        email=user.email,
        username=user.username,
        hashed_password=hashed_password,
        is_verified=False,
        verification_token=verification_token
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user(db: Session, user_id: int, user_update: schemas.UserUpdate) -> Optional[models.User]:
    """Update user information."""
    db_user = get_user_by_id(db, user_id)
    if db_user is None:
        return None
    
    update_dict = user_update.model_dump(exclude_unset=True)
    
    if 'username' in update_dict and update_dict['username'] != db_user.username:
        existing_user = get_user_by_username(db, update_dict['username'])
        if existing_user:
            raise ValueError("Username already taken")
        db_user.username = update_dict['username']
    
    if 'email' in update_dict and update_dict['email'] != db_user.email:
        existing_user = get_user_by_email(db, update_dict['email'])
        if existing_user and existing_user.id != db_user.id:
            raise ValueError("Email already registered")
        db_user.email = update_dict['email']
    
    if 'password' in update_dict:
        db_user.hashed_password = update_dict['password']
    
    db.commit()
    db.refresh(db_user)
    return db_user


def deactivate_user(db: Session, user_id: int) -> Optional[models.User]:
    """Deactivate a user account (soft delete)."""
    db_user = get_user_by_id(db, user_id)
    if db_user is None:
        return None
    
    db_user.is_active = False
    db_user.deactivated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(db_user)
    return db_user


def reactivate_user(db: Session, user_id: int) -> Optional[models.User]:
    """Reactivate a deactivated user account (within 90-day window)."""
    db_user = get_user_by_id(db, user_id)
    if db_user is None:
        return None
    
    if db_user.deactivated_at is None:
        raise ValueError("Account was not deactivated")
    
    days_since_deactivation = (datetime.now(timezone.utc) - db_user.deactivated_at.replace(tzinfo=timezone.utc)).days
    if days_since_deactivation > 90:
        raise ValueError("Account cannot be reactivated after 90 days")
    
    db_user.is_active = True
    db_user.deactivated_at = None
    db.commit()
    db.refresh(db_user)
    return db_user


def update_privacy_settings(db: Session, user_id: int, privacy_settings: schemas.PrivacySettingsUpdate) -> Optional[models.User]:
    """Update user's privacy settings."""
    db_user = get_user_by_id(db, user_id)
    if db_user is None:
        return None
    
    update_dict = privacy_settings.model_dump(exclude_unset=True)
    
    if 'movies_private' in update_dict:
        db_user.movies_private = update_dict['movies_private']
    if 'tv_shows_private' in update_dict:
        db_user.tv_shows_private = update_dict['tv_shows_private']
    if 'anime_private' in update_dict:
        db_user.anime_private = update_dict['anime_private']
    if 'video_games_private' in update_dict:
        db_user.video_games_private = update_dict['video_games_private']
    if 'music_private' in update_dict:
        db_user.music_private = update_dict['music_private']
    if 'books_private' in update_dict:
        db_user.books_private = update_dict['books_private']
    if 'manga_private' in update_dict:
        db_user.manga_private = update_dict['manga_private']
    if 'podcasts_private' in update_dict:
        db_user.podcasts_private = update_dict['podcasts_private']
    if 'audiobooks_private' in update_dict:
        db_user.audiobooks_private = update_dict['audiobooks_private']
    if 'statistics_private' in update_dict:
        db_user.statistics_private = update_dict['statistics_private']
    
    db.commit()
    db.refresh(db_user)
    return db_user


def get_privacy_settings(db: Session, user_id: int) -> Optional[schemas.PrivacySettings]:
    """Get user's privacy settings."""
    db_user = get_user_by_id(db, user_id)
    if db_user is None:
        return None
    
    return schemas.PrivacySettings(
        movies_private=db_user.movies_private,
        tv_shows_private=db_user.tv_shows_private,
        anime_private=db_user.anime_private,
        video_games_private=db_user.video_games_private,
        music_private=db_user.music_private,
        books_private=db_user.books_private,
        manga_private=db_user.manga_private,
        podcasts_private=db_user.podcasts_private,
        audiobooks_private=db_user.audiobooks_private,
        statistics_private=db_user.statistics_private
    )


def update_tab_visibility(db: Session, user_id: int, tab_visibility: schemas.TabVisibilityUpdate) -> Optional[models.User]:
    """Update user's tab visibility settings."""
    db_user = get_user_by_id(db, user_id)
    if db_user is None:
        return None
    
    update_dict = tab_visibility.model_dump(exclude_unset=True)
    
    if 'movies_visible' in update_dict:
        db_user.movies_visible = update_dict['movies_visible']
    if 'tv_shows_visible' in update_dict:
        db_user.tv_shows_visible = update_dict['tv_shows_visible']
    if 'anime_visible' in update_dict:
        db_user.anime_visible = update_dict['anime_visible']
    if 'video_games_visible' in update_dict:
        db_user.video_games_visible = update_dict['video_games_visible']
    if 'music_visible' in update_dict:
        db_user.music_visible = update_dict['music_visible']
    if 'books_visible' in update_dict:
        db_user.books_visible = update_dict['books_visible']
    if 'manga_visible' in update_dict:
        db_user.manga_visible = update_dict['manga_visible']
    if 'podcasts_visible' in update_dict:
        db_user.podcasts_visible = update_dict['podcasts_visible']
    if 'audiobooks_visible' in update_dict:
        db_user.audiobooks_visible = update_dict['audiobooks_visible']
    
    db.commit()
    db.refresh(db_user)
    return db_user


def get_tab_visibility(db: Session, user_id: int) -> Optional[schemas.TabVisibility]:
    """Get user's tab visibility settings."""
    db_user = get_user_by_id(db, user_id)
    if db_user is None:
        return None
    
    return schemas.TabVisibility(
        movies_visible=db_user.movies_visible,
        tv_shows_visible=db_user.tv_shows_visible,
        anime_visible=db_user.anime_visible,
        video_games_visible=db_user.video_games_visible,
        music_visible=db_user.music_visible,
        books_visible=db_user.books_visible,
        manga_visible=db_user.manga_visible,
        podcasts_visible=db_user.podcasts_visible,
        audiobooks_visible=db_user.audiobooks_visible
    )


def update_profile_picture(
    db: Session, 
    user_id: int, 
    profile_picture_url: str,
    profile_picture_data: bytes = None,
    profile_picture_mime_type: str = None
) -> Optional[models.User]:
    """Update user's profile picture (database storage)."""
    db_user = get_user_by_id(db, user_id)
    if db_user is None:
        return None
    
    db_user.profile_picture_url = profile_picture_url
    if profile_picture_data is not None:
        db_user.profile_picture_data = profile_picture_data
    if profile_picture_mime_type is not None:
        db_user.profile_picture_mime_type = profile_picture_mime_type
    db.commit()
    db.refresh(db_user)
    return db_user


def reset_profile_picture(db: Session, user_id: int) -> Optional[models.User]:
    """Reset user's profile picture (clear all fields)."""
    db_user = get_user_by_id(db, user_id)
    if db_user is None:
        return None
    
    db_user.profile_picture_url = None
    db_user.profile_picture_data = None
    db_user.profile_picture_mime_type = None
    db.commit()
    db.refresh(db_user)
    return db_user

