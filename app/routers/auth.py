"""
Authentication endpoints for the OmniTrackr API.
"""
import os
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .. import crud, schemas, models, auth, email as email_utils
from ..dependencies import get_db

router = APIRouter(prefix="/auth", tags=["auth"])




@router.post("/register", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
async def register(
    user: schemas.UserCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """Register a new user and send verification email."""
    
    is_valid, error_msg = auth.validate_password_strength(user.password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    if crud.get_user_by_email(db, user.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    if crud.get_user_by_username(db, user.username):
        raise HTTPException(status_code=400, detail="Username already taken")
    
    verification_token = email_utils.generate_verification_token(user.email)
    
    hashed_password = auth.get_password_hash(user.password)
    db_user = crud.create_user(db, user, hashed_password, verification_token)
    
    try:
        await email_utils.send_verification_email(user.email, user.username, verification_token)
    except Exception as e:
        print(f"Failed to send verification email: {e}")
    
    return db_user


@router.post("/login", response_model=schemas.Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Login to get access token. Users can log in using either their username or email."""
    
    user = crud.get_user_by_username_or_email(db, form_data.username)
    
    if user and user.locked_until and user.locked_until > datetime.now(timezone.utc):
        remaining_minutes = int((user.locked_until - datetime.now(timezone.utc)).total_seconds() / 60)
        raise HTTPException(
            status_code=423,
            detail=f"Account is locked due to too many failed login attempts. Try again in {remaining_minutes} minutes.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if user and user.locked_until and user.locked_until <= datetime.now(timezone.utc):
        user.locked_until = None
        user.failed_login_attempts = 0
        db.commit()
    
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        client_ip = request.client.host if request.client else "unknown"
        if user:
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= 5:
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
                print(f"SECURITY: Account locked - Username: {form_data.username}, IP: {client_ip}, Failed attempts: {user.failed_login_attempts}")
            else:
                print(f"SECURITY: Failed login attempt - Username: {form_data.username}, IP: {client_ip}, Attempts: {user.failed_login_attempts}")
            db.commit()
        else:
            print(f"SECURITY: Failed login attempt - Username: {form_data.username} (not found), IP: {client_ip}")
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()
    
    if not user.is_active:
        if user.deactivated_at:
            days_since_deactivation = (datetime.now(timezone.utc) - user.deactivated_at.replace(tzinfo=timezone.utc)).days
            if days_since_deactivation > 90:
                raise HTTPException(
                    status_code=403,
                    detail="Account has been permanently deactivated. It cannot be reactivated after 90 days.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            else:
                # Account is deactivated but within 90-day window
                raise HTTPException(
                    status_code=403,
                    detail=f"Account is deactivated. You can reactivate it within {90 - days_since_deactivation} days. Please use the reactivate endpoint.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        else:
            raise HTTPException(
                status_code=403,
                detail="Account is deactivated. Please reactivate your account.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    if not user.is_verified:
        raise HTTPException(
            status_code=403,
            detail="Please verify your email address before logging in. Check your inbox for the verification link.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = auth.create_access_token(data={"sub": user.username})
    token_response = schemas.Token(access_token=access_token, token_type="bearer", user=user)
    return JSONResponse(
        content=jsonable_encoder(token_response),
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )


@router.get("/verify-email")
async def verify_email(token: str, db: Session = Depends(get_db)):
    """Verify user email with token (handles both initial verification and email change)."""
    # First, try regular email verification (most common case)
    try:
        email = email_utils.verify_token(token, max_age=3600)  # 1 hour expiration
        # This is a regular email verification token
        user = crud.get_user_by_email(db, email)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if user.is_verified:
            return {"message": "Email already verified"}
        
        # Mark user as verified
        user.is_verified = True
        user.verification_token = None
        db.commit()
        db.refresh(user)
        
        return {"message": "Email verified successfully! You can now use all features."}
    except HTTPException:
        raise
    except Exception:
        # Not a regular email verification token, try email change token
        try:
            old_email, new_email = email_utils.verify_email_change_token(token, max_age=3600)
            # This is an email change verification
            user = crud.get_user_by_email(db, old_email)
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Verify old_email matches the user's current email
            if user.email != old_email:
                raise HTTPException(status_code=400, detail="Email change token does not match current email")
            
            if not user.verification_token or not user.verification_token.startswith("email_change:"):
                raise HTTPException(status_code=400, detail="No pending email change found")
            
            parts = user.verification_token.split(":", 2)
            if len(parts) != 3:
                raise HTTPException(status_code=400, detail="Invalid email change token format")
            
            stored_token = parts[1]
            stored_new_email = parts[2]
            
            if stored_new_email != new_email:
                raise HTTPException(status_code=400, detail="Email mismatch in token")
            
            from urllib.parse import unquote
            if stored_token != token:
                # Try URL-decoded version
                decoded_token = unquote(token)
                if stored_token != decoded_token:
                    raise HTTPException(status_code=400, detail="Invalid email change token")
            
            existing_user = crud.get_user_by_email(db, new_email)
            if existing_user and existing_user.id != user.id:
                raise HTTPException(status_code=400, detail="New email is already registered")
            
            user.email = new_email
            user.verification_token = None
            db.commit()
            db.refresh(user)
            
            return {"message": "Email changed successfully! Your new email is now verified."}
        except HTTPException:
            raise
        except Exception:
            # Neither token type worked
            raise HTTPException(status_code=400, detail="Invalid or expired verification token")


@router.post("/resend-verification")
async def resend_verification_email(
    email: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Resend verification email to user."""
    
    user = crud.get_user_by_email(db, email)
    
    # Don't reveal if email exists for security (same behavior as password reset)
    if not user:
        return {"message": "If that email is registered and unverified, a verification email has been sent."}
    
    # If already verified, don't send another email
    if user.is_verified:
        return {"message": "Email is already verified. You can log in."}
    
    # Generate new verification token
    verification_token = email_utils.generate_verification_token(user.email)
    user.verification_token = verification_token
    db.commit()
    
    # Check if email credentials are configured before attempting to send
    mail_username = os.getenv("MAIL_USERNAME", "")
    mail_password = os.getenv("MAIL_PASSWORD", "")
    
    if not mail_username or not mail_password:
        print(f"WARNING: Email credentials not configured (MAIL_USERNAME or MAIL_PASSWORD missing).")
        print(f"WARNING: Verification email will NOT be sent to {user.email}.")
        print(f"WARNING: Email will only be printed to console in development mode.")
        verification_url = f"{email_utils.APP_URL}/?token={verification_token}&email_verified=true"
        print(f"INFO: Verification URL for {user.email}: {verification_url}")
        # Still return success message for security (don't reveal email wasn't sent)
        return {"message": "If that email is registered and unverified, a verification email has been sent."}
    
    # Send verification email (async, non-blocking)
    email_sent = False
    try:
        await email_utils.send_verification_email(user.email, user.username, verification_token)
        email_sent = True
        print(f"INFO: Verification email sent successfully to {user.email}")
    except Exception as e:
        error_msg = str(e)
        print(f"ERROR: Failed to send verification email to {user.email}")
        print(f"ERROR Details: {error_msg}")
        print(f"ERROR Type: {type(e).__name__}")
        import traceback
        print(f"ERROR Traceback: {traceback.format_exc()}")
        # Check if it's a configuration issue
        if "MAIL_USERNAME" in error_msg or "MAIL_PASSWORD" in error_msg or "credentials" in error_msg.lower() or "smtp" in error_msg.lower():
            print(f"WARNING: Email credentials may be incorrect or SMTP server unreachable.")
            print(f"WARNING: Check MAIL_USERNAME, MAIL_PASSWORD, MAIL_SERVER, and MAIL_PORT environment variables.")
        verification_url = f"{email_utils.APP_URL}/?token={verification_token}&email_verified=true"
        print(f"INFO: Fallback verification URL for {user.email}: {verification_url}")
        email_sent = False
    
    if not email_sent:
        print(f"WARNING: Verification email was NOT sent to {user.email}, but user received success message.")
        print(f"WARNING: Check server logs above for email sending errors.")
    
    return {"message": "If that email is registered and unverified, a verification email has been sent."}


@router.post("/request-password-reset")
async def request_password_reset(
    email: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Request a password reset email."""
    
    user = crud.get_user_by_email(db, email)
    if not user:
        return {"message": "If that email is registered, you will receive a password reset link."}
    
    reset_token = email_utils.generate_reset_token(email)
    
    user.reset_token = auth.hash_token(reset_token)
    user.reset_token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
    db.commit()
    
    try:
        await email_utils.send_password_reset_email(email, user.username, reset_token)
    except Exception as e:
        print(f"Failed to send password reset email: {e}")
    
    return {"message": "If that email is registered, you will receive a password reset link."}


@router.post("/reset-password")
async def reset_password(token: str, new_password: str, db: Session = Depends(get_db)):
    """Reset password with valid token."""
    user = None
    if token.startswith("$2"):
        user = db.query(models.User).filter(models.User.reset_token == token).first()
        if not user:
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    else:
        try:
            email = email_utils.verify_reset_token(token, max_age=3600)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")
        
        user = crud.get_user_by_email(db, email)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
    
    if not user.reset_token_expires or user.reset_token_expires.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Reset token has expired")
    
    if not user.reset_token:
        raise HTTPException(status_code=400, detail="Invalid reset token")
    
    if user.reset_token.startswith("$2"):
        if token.startswith("$2"):
            if not secrets.compare_digest(user.reset_token, token):
                raise HTTPException(status_code=400, detail="Invalid reset token")
        else:
            if not auth.verify_token_hash(token, user.reset_token):
                raise HTTPException(status_code=400, detail="Invalid reset token")
    else:
        if not secrets.compare_digest(user.reset_token, token):
            raise HTTPException(status_code=400, detail="Invalid reset token")
    
    is_valid, error_msg = auth.validate_password_strength(new_password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    user.hashed_password = auth.get_password_hash(new_password)
    user.reset_token = None
    user.reset_token_expires = None
    db.commit()
    db.refresh(user)
    
    return {"message": "Password reset successfully! You can now login with your new password."}


@router.post("/reactivate", response_model=schemas.User)
async def reactivate_account_public(
    reactivate: schemas.AccountReactivate,
    db: Session = Depends(get_db)
):
    """Reactivate a deactivated account via public endpoint (within 90-day window)."""
    # Find user by username or email
    user = None
    if reactivate.username:
        user = crud.get_user_by_username(db, reactivate.username)
        if not user:
            user = crud.get_user_by_email(db, reactivate.username)
    elif reactivate.email:
        user = crud.get_user_by_email(db, reactivate.email)
    else:
        raise HTTPException(status_code=400, detail="Username or email is required")
    
    if not user:
        # Don't reveal if account exists for security
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials or account not found"
        )
    
    # Verify password
    if not auth.verify_password(reactivate.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials or account not found"
        )
    
    # Check if account is already active
    if user.is_active:
        raise HTTPException(status_code=400, detail="Account is already active")
    
    # Check if account was deactivated
    if not user.deactivated_at:
        raise HTTPException(status_code=400, detail="Account was not deactivated")
    
    # Reactivate account
    try:
        reactivated_user = crud.reactivate_user(db, user.id)
        if reactivated_user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return reactivated_user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

