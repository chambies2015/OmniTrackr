"""
Custom Tab endpoints for the OmniTrackr API.
"""
import io
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from .. import crud, schemas, models
from ..dependencies import get_db, get_current_user

router = APIRouter(prefix="/custom-tabs", tags=["custom-tabs"])


def _parse_item_field_values(item) -> dict:
    """Helper function to parse field_values from JSON string."""
    if item.field_values:
        try:
            return json.loads(item.field_values)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _item_to_dict(item) -> dict:
    """Helper function to convert CustomTabItem to dict with parsed field_values."""
    return {
        "id": item.id,
        "tab_id": item.tab_id,
        "title": item.title,
        "poster_url": item.poster_url,
        "created_at": item.created_at,
        "field_values": _parse_item_field_values(item)
    }


@router.get("/", response_model=List[schemas.CustomTab])
async def list_custom_tabs(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud.get_custom_tabs(db, current_user.id)


@router.get("/{tab_id}", response_model=schemas.CustomTab)
async def get_custom_tab(
    tab_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_tab = crud.get_custom_tab_by_id(db, current_user.id, tab_id)
    if db_tab is None:
        raise HTTPException(status_code=404, detail="Custom tab not found")
    return db_tab


@router.post("/", response_model=schemas.CustomTab, status_code=201)
async def create_custom_tab(
    tab: schemas.CustomTabCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        return crud.create_custom_tab(db, current_user.id, tab)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create custom tab: {str(e)}")


@router.put("/{tab_id}", response_model=schemas.CustomTab)
async def update_custom_tab(
    tab_id: int,
    tab: schemas.CustomTabUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        db_tab = crud.update_custom_tab(db, current_user.id, tab_id, tab)
        if db_tab is None:
            raise HTTPException(status_code=404, detail="Custom tab not found")
        return db_tab
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update custom tab: {str(e)}")


@router.delete("/{tab_id}", response_model=schemas.CustomTab)
async def delete_custom_tab(
    tab_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_tab = crud.delete_custom_tab(db, current_user.id, tab_id)
    if db_tab is None:
        raise HTTPException(status_code=404, detail="Custom tab not found")
    return db_tab


@router.get("/{tab_id}/items", response_model=List[schemas.CustomTabItem])
async def list_custom_tab_items(
    tab_id: int,
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    order: Optional[str] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = crud.get_custom_tab_items(
        db, current_user.id, tab_id, search=search, sort_by=sort_by, order=order
    )
    
    return [schemas.CustomTabItem(**_item_to_dict(item)) for item in items]


@router.get("/{tab_id}/items/{item_id}", response_model=schemas.CustomTabItem)
async def get_custom_tab_item(
    tab_id: int,
    item_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_item = crud.get_custom_tab_item_by_id(db, current_user.id, tab_id, item_id)
    if db_item is None:
        raise HTTPException(status_code=404, detail="Custom tab item not found")
    
    return schemas.CustomTabItem(**_item_to_dict(db_item))


@router.post("/{tab_id}/items", response_model=schemas.CustomTabItem, status_code=201)
async def create_custom_tab_item(
    tab_id: int,
    item: schemas.CustomTabItemCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_item, error_msg = crud.create_custom_tab_item(db, current_user.id, tab_id, item)
    if db_item is None:
        if error_msg:
            raise HTTPException(status_code=400, detail=error_msg)
        raise HTTPException(status_code=404, detail="Custom tab not found")
    
    return schemas.CustomTabItem(**_item_to_dict(db_item))


@router.put("/{tab_id}/items/{item_id}", response_model=schemas.CustomTabItem)
async def update_custom_tab_item(
    tab_id: int,
    item_id: int,
    item: schemas.CustomTabItemUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_item, error_msg = crud.update_custom_tab_item(db, current_user.id, tab_id, item_id, item)
    if db_item is None:
        if error_msg:
            raise HTTPException(status_code=400, detail=error_msg)
        raise HTTPException(status_code=404, detail="Custom tab item not found")
    
    return schemas.CustomTabItem(**_item_to_dict(db_item))


@router.delete("/{tab_id}/items/{item_id}", response_model=schemas.CustomTabItem)
async def delete_custom_tab_item(
    tab_id: int,
    item_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_item = crud.delete_custom_tab_item(db, current_user.id, tab_id, item_id)
    if db_item is None:
        raise HTTPException(status_code=404, detail="Custom tab item not found")
    
    return schemas.CustomTabItem(**_item_to_dict(db_item))


@router.post("/{tab_id}/items/{item_id}/poster", response_model=schemas.CustomTabItem)
async def upload_custom_tab_item_poster(
    tab_id: int,
    item_id: int,
    request: Request,
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_item = crud.get_custom_tab_item_by_id(db, current_user.id, tab_id, item_id)
    if db_item is None:
        raise HTTPException(status_code=404, detail="Custom tab item not found")
    
    db_tab = crud.get_custom_tab_by_id(db, current_user.id, tab_id)
    if db_tab is None or not db_tab.allow_uploads:
        raise HTTPException(status_code=403, detail="Poster uploads not allowed for this tab")
    
    allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Allowed types: JPEG, PNG, GIF, WebP"
        )
    
    file_content = await file.read()
    if len(file_content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds 5MB limit")
    
    try:
        file_signature = file_content[:12]
        detected_format = None
        
        if file_signature[:3] == b'\xff\xd8\xff':
            detected_format = 'jpeg'
        elif file_signature[:8] == b'\x89PNG\r\n\x1a\n':
            detected_format = 'png'
        elif file_signature[:6] in [b'GIF87a', b'GIF89a']:
            detected_format = 'gif'
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
    
    if not PIL_AVAILABLE:
        raise HTTPException(
            status_code=500,
            detail="Image processing is not available. Please install Pillow."
        )
    
    try:
        image = Image.open(io.BytesIO(file_content))
        
        if image.mode == 'RGBA':
            pass
        elif image.mode in ('LA', 'P'):
            image = image.convert('RGBA')
        elif image.mode == 'L':
            image = image.convert('RGB')
        elif image.mode not in ('RGB', 'RGBA'):
            image = image.convert('RGB')
        
        max_size = (512, 512)
        if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        mime_type = "image/webp"
        
        max_target_size = 200 * 1024
        quality = 80
        image_data = None
        
        for attempt in range(3):
            output = io.BytesIO()
            
            save_kwargs = {
                'format': 'WEBP',
                'quality': quality,
                'method': 6,
                'lossless': False
            }
            
            if image.mode == 'RGBA':
                image.save(output, **save_kwargs)
            else:
                image.save(output, **save_kwargs)
            
            image_data = output.getvalue()
            
            if len(image_data) <= max_target_size or attempt >= 2:
                break
            
            quality = max(60, quality - 10)
        
        if len(image_data) > 300 * 1024:
            output = io.BytesIO()
            image.save(output, format='WEBP', quality=70, method=6, lossless=False)
            image_data = output.getvalue()
        
        poster_url = f"/custom-tab-posters/{item_id}"
        updated_item = crud.update_custom_tab_item_poster(
            db,
            current_user.id,
            tab_id,
            item_id,
            poster_url=poster_url,
            poster_data=image_data,
            poster_mime_type=mime_type
        )
        
        if updated_item is None:
            raise HTTPException(status_code=404, detail="Custom tab item not found")
        
        return schemas.CustomTabItem(**_item_to_dict(updated_item))
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error processing image: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to process image: {str(e)}"
        )
