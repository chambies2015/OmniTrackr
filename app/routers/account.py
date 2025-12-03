"""
Account management endpoints for the OmniTrackr API.
"""
import io
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request, status
from sqlalchemy.orm import Session

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from .. import crud, schemas, models, auth, email as email_utils
from ..dependencies import get_db, get_current_user

router = APIRouter(prefix="/account", tags=["account"])


@router.get("/me", response_model=schemas.User)
async def get_current_account(current_user: models.User = Depends(get_current_user)):
    """Get current user's account information."""
    return current_user


@router.put("/username", response_model=schemas.User)
async def change_username(
    username_change: schemas.UsernameChange,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change username (requires password confirmation)."""
    # Verify password
    if not auth.verify_password(username_change.password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect password")
    
    # Check if username is already taken
    existing_user = crud.get_user_by_username(db, username_change.new_username)
    if existing_user and existing_user.id != current_user.id:
        raise HTTPException(status_code=400, detail="Username already taken")
    
    # Update username
    try:
        user_update = schemas.UserUpdate(username=username_change.new_username)
        updated_user = crud.update_user(db, current_user.id, user_update)
        if updated_user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return updated_user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/email", response_model=dict)
async def change_email(
    email_change: schemas.EmailChange,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change email address (requires password + sends verification email to new address)."""
    # Verify password
    if not auth.verify_password(email_change.password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect password")
    
    # Check if email is already registered
    existing_user = crud.get_user_by_email(db, email_change.new_email)
    if existing_user and existing_user.id != current_user.id:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Generate email change verification token
    email_change_token = email_utils.generate_email_change_token(current_user.email, email_change.new_email)
    
    # Store the new email and token temporarily (we'll update email after verification)
    # For now, store in verification_token field with a special prefix
    current_user.verification_token = f"email_change:{email_change_token}:{email_change.new_email}"
    db.commit()
    
    # Send verification email to new address
    try:
        await email_utils.send_email_change_verification_email(
            email_change.new_email,
            current_user.username,
            email_change_token
        )
    except Exception as e:
        print(f"Failed to send email change verification email: {e}")
        # Don't fail the request, but log the error
    
    return {
        "message": "Verification email sent to new address. Please verify your new email to complete the change."
    }


@router.put("/password", response_model=dict)
async def change_password(
    password_change: schemas.PasswordChange,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change password (requires current password)."""
    # Verify current password
    if not auth.verify_password(password_change.current_password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect current password")
    
    # Hash new password and update
    hashed_new_password = auth.get_password_hash(password_change.new_password)
    user_update = schemas.UserUpdate(password=hashed_new_password)
    updated_user = crud.update_user(db, current_user.id, user_update)
    
    if updated_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "Password changed successfully"}


@router.put("/privacy", response_model=schemas.PrivacySettings)
async def update_privacy_settings(
    privacy_update: schemas.PrivacySettingsUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user's privacy settings."""
    updated_user = crud.update_privacy_settings(db, current_user.id, privacy_update)
    
    if updated_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    return crud.get_privacy_settings(db, current_user.id)


@router.get("/privacy", response_model=schemas.PrivacySettings)
async def get_privacy_settings(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's current privacy settings."""
    privacy_settings = crud.get_privacy_settings(db, current_user.id)
    
    if privacy_settings is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    return privacy_settings


@router.put("/tab-visibility", response_model=schemas.TabVisibility)
async def update_tab_visibility(
    tab_visibility_update: schemas.TabVisibilityUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user's tab visibility settings."""
    updated_user = crud.update_tab_visibility(db, current_user.id, tab_visibility_update)
    
    if updated_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    return crud.get_tab_visibility(db, current_user.id)


@router.get("/tab-visibility", response_model=schemas.TabVisibility)
async def get_tab_visibility(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's current tab visibility settings."""
    tab_visibility = crud.get_tab_visibility(db, current_user.id)
    
    if tab_visibility is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    return tab_visibility


@router.post("/profile-picture", response_model=schemas.User)
async def upload_profile_picture(
    request: Request,
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload a profile picture with content validation and image processing."""
    # Validate file type
    allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Allowed types: JPEG, PNG, GIF, WebP"
        )
    
    # Validate file size (max 5MB)
    file_content = await file.read()
    if len(file_content) > 5 * 1024 * 1024:  # 5MB
        raise HTTPException(status_code=400, detail="File size exceeds 5MB limit")
    
    # Content validation: Verify file is actually an image using magic bytes
    try:
        # Check magic bytes (file signature) to verify it's actually an image
        file_signature = file_content[:12]  # Read first 12 bytes
        detected_format = None
        
        # Check JPEG
        if file_signature[:3] == b'\xff\xd8\xff':
            detected_format = 'jpeg'
        # Check PNG
        elif file_signature[:8] == b'\x89PNG\r\n\x1a\n':
            detected_format = 'png'
        # Check GIF
        elif file_signature[:6] in [b'GIF87a', b'GIF89a']:
            detected_format = 'gif'
        # Check WebP (RIFF...WEBP)
        elif file_signature[:4] == b'RIFF' and b'WEBP' in file_content[:20]:
            detected_format = 'webp'
        
        if not detected_format:
            raise HTTPException(
                status_code=400,
                detail="File is not a valid image. Content validation failed."
            )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(
            status_code=400,
            detail="Failed to validate image content. Please ensure the file is a valid image."
        )
    
    # Process and optimize image
    if not PIL_AVAILABLE:
        raise HTTPException(
            status_code=500,
            detail="Image processing is not available. Please install Pillow."
        )
    
    try:
        # Open image from bytes
        image = Image.open(io.BytesIO(file_content))
        
        # Convert to RGB/RGBA for processing
        # WebP supports transparency, so preserve RGBA if present
        if image.mode == 'RGBA':
            # Keep RGBA for WebP (supports transparency)
            pass
        elif image.mode in ('LA', 'P'):
            # Convert palette/grayscale with alpha to RGBA
            image = image.convert('RGBA')
        elif image.mode == 'L':
            # Grayscale to RGB
            image = image.convert('RGB')
        elif image.mode not in ('RGB', 'RGBA'):
            # Convert other modes to RGB
            image = image.convert('RGB')
        
        # Resize if image is too large (max 512x512 for profile pictures - optimized size)
        max_size = (512, 512)
        if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Always convert to WebP for best compression (typically 25-35% smaller than JPEG)
        # WebP provides excellent quality at smaller file sizes
        mime_type = "image/webp"
        
        # Save optimized image to memory with adaptive quality
        # Start with quality 80, reduce if file is still too large
        max_target_size = 200 * 1024  # Target: 200KB max
        quality = 80
        image_data = None
        
        for attempt in range(3):  # Try up to 3 quality levels
            output = io.BytesIO()
            
            # Save as WebP with current quality
            save_kwargs = {
                'format': 'WEBP',
                'quality': quality,
                'method': 6,  # Best compression method (slower but smaller)
                'lossless': False
            }
            
            # If image has transparency, ensure we preserve it
            if image.mode == 'RGBA':
                # WebP supports transparency natively
                image.save(output, **save_kwargs)
            else:
                # RGB image
                image.save(output, **save_kwargs)
            
            image_data = output.getvalue()
            
            # If file size is acceptable or we've tried enough, break
            if len(image_data) <= max_target_size or attempt >= 2:
                break
            
            # Reduce quality for next attempt
            quality = max(60, quality - 10)  # Don't go below 60
        
        # If still too large after optimization, use more aggressive compression
        if len(image_data) > 300 * 1024:  # Still over 300KB
            output = io.BytesIO()
            image.save(output, format='WEBP', quality=70, method=6, lossless=False)
            image_data = output.getvalue()
        
        # Update database with image data, MIME type, and virtual URL
        profile_picture_url = f"/profile-pictures/{current_user.id}"
        updated_user = crud.update_profile_picture(
            db, 
            current_user.id, 
            profile_picture_url=profile_picture_url,
            profile_picture_data=image_data,
            profile_picture_mime_type=mime_type
        )
        
        if updated_user is None:
            raise HTTPException(status_code=404, detail="User not found")
        
        return updated_user
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error processing image: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to process image: {str(e)}"
        )


@router.delete("/profile-picture", response_model=schemas.User)
async def reset_profile_picture(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reset/remove profile picture."""
    # Update database to clear profile picture data
    updated_user = crud.reset_profile_picture(db, current_user.id)
    
    if updated_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    return updated_user


@router.post("/deactivate", response_model=dict)
async def deactivate_account(
    deactivate: schemas.AccountDeactivate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Deactivate account (soft delete, requires password confirmation)."""
    # Verify password
    if not auth.verify_password(deactivate.password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect password")
    
    # Deactivate account
    deactivated_user = crud.deactivate_user(db, current_user.id)
    if deactivated_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "message": "Account deactivated. You can reactivate within 90 days. After that, your account will be permanently deleted."
    }


@router.post("/reactivate", response_model=schemas.User)
async def reactivate_account(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reactivate a deactivated account (within 90-day window). Requires authentication."""
    if current_user.is_active:
        raise HTTPException(status_code=400, detail="Account is already active")
    
    try:
        reactivated_user = crud.reactivate_user(db, current_user.id)
        if reactivated_user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return reactivated_user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

