"""
User CRUD operations for the OmniTrackr API.
"""
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session, load_only
from sqlalchemy import or_

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


def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    """Get user by email."""
    return db.query(models.User).filter(models.User.email == email).first()


def get_user_by_username_or_email(db: Session, username_or_email: str) -> Optional[models.User]:
    """Get user by username or email (optimized single query)."""
    return db.query(models.User).filter(
        or_(
            models.User.username == username_or_email,
            models.User.email == username_or_email
        )
    ).first()


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
    
    update_dict = user_update.dict(exclude_unset=True)
    
    if 'username' in update_dict and update_dict['username'] != db_user.username:
        existing_user = get_user_by_username(db, update_dict['username'])
        if existing_user:
            raise ValueError("Username already taken")
        db_user.username = update_dict['username']
    
    if 'email' in update_dict and update_dict['email'] != db_user.email:
        existing_user = get_user_by_email(db, update_dict['email'])
        if existing_user:
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
    
    update_dict = privacy_settings.dict(exclude_unset=True)
    
    if 'movies_private' in update_dict:
        db_user.movies_private = update_dict['movies_private']
    if 'tv_shows_private' in update_dict:
        db_user.tv_shows_private = update_dict['tv_shows_private']
    if 'anime_private' in update_dict:
        db_user.anime_private = update_dict['anime_private']
    if 'video_games_private' in update_dict:
        db_user.video_games_private = update_dict['video_games_private']
    if 'statistics_private' in update_dict:
        db_user.statistics_private = update_dict['statistics_private']
    if 'reviews_public' in update_dict:
        db_user.reviews_public = update_dict['reviews_public']
    
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
        statistics_private=db_user.statistics_private,
        reviews_public=db_user.reviews_public
    )


def update_tab_visibility(db: Session, user_id: int, tab_visibility: schemas.TabVisibilityUpdate) -> Optional[models.User]:
    """Update user's tab visibility settings."""
    db_user = get_user_by_id(db, user_id)
    if db_user is None:
        return None
    
    update_dict = tab_visibility.dict(exclude_unset=True)
    
    if 'movies_visible' in update_dict:
        db_user.movies_visible = update_dict['movies_visible']
    if 'tv_shows_visible' in update_dict:
        db_user.tv_shows_visible = update_dict['tv_shows_visible']
    if 'anime_visible' in update_dict:
        db_user.anime_visible = update_dict['anime_visible']
    if 'video_games_visible' in update_dict:
        db_user.video_games_visible = update_dict['video_games_visible']
    
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
        video_games_visible=db_user.video_games_visible
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

