"""
Custom Tab CRUD operations for the OmniTrackr API.
"""
import json
import re
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import asc, desc

from .. import models, schemas

MAX_CUSTOM_TABS_PER_USER = 20
MAX_FIELDS_PER_TAB = 30
MAX_ITEMS_PER_TAB = 10000


def _generate_slug(name: str) -> str:
    slug = re.sub(r'[^\w\s-]', '', name.lower())
    slug = re.sub(r'[-\s]+', '-', slug)
    slug = slug.strip('-')
    if not slug:
        slug = 'custom-tab'
    if len(slug) > 100:
        slug = slug[:100]
    return slug


def get_custom_tabs(db: Session, user_id: int) -> List[models.CustomTab]:
    return db.query(models.CustomTab).options(
        joinedload(models.CustomTab.fields)
    ).filter(
        models.CustomTab.user_id == user_id
    ).order_by(models.CustomTab.created_at.asc()).all()


def get_custom_tab_by_id(db: Session, user_id: int, tab_id: int) -> Optional[models.CustomTab]:
    return db.query(models.CustomTab).options(
        joinedload(models.CustomTab.fields)
    ).filter(
        models.CustomTab.id == tab_id,
        models.CustomTab.user_id == user_id
    ).first()


def get_custom_tab_by_slug(db: Session, user_id: int, slug: str) -> Optional[models.CustomTab]:
    return db.query(models.CustomTab).filter(
        models.CustomTab.slug == slug,
        models.CustomTab.user_id == user_id
    ).first()


def create_custom_tab(db: Session, user_id: int, tab: schemas.CustomTabCreate) -> models.CustomTab:
    existing_tabs_count = db.query(models.CustomTab).filter(
        models.CustomTab.user_id == user_id
    ).count()
    
    if existing_tabs_count >= MAX_CUSTOM_TABS_PER_USER:
        raise ValueError(f"Maximum of {MAX_CUSTOM_TABS_PER_USER} custom tabs allowed per user")
    
    if len(tab.fields) > MAX_FIELDS_PER_TAB:
        raise ValueError(f"Maximum of {MAX_FIELDS_PER_TAB} fields allowed per tab")
    
    field_keys = [f.key for f in tab.fields]
    if len(field_keys) != len(set(field_keys)):
        raise ValueError("Duplicate field keys are not allowed")
    
    for field in tab.fields:
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', field.key):
            raise ValueError(f"Field key '{field.key}' must start with a letter or underscore and contain only alphanumeric characters and underscores")
    
    if tab.source_type not in ('none', 'omdb', 'jikan', 'rawg'):
        raise ValueError("source_type must be one of: none, omdb, jikan, rawg")
    
    valid_field_types = ('text', 'number', 'date', 'boolean', 'rating', 'review', 'status')
    for field in tab.fields:
        if field.field_type not in valid_field_types:
            raise ValueError(f"Invalid field_type '{field.field_type}'. Must be one of: {', '.join(valid_field_types)}")
    
    base_slug = _generate_slug(tab.name)
    slug = base_slug
    counter = 1
    
    while db.query(models.CustomTab).filter(
        models.CustomTab.user_id == user_id,
        models.CustomTab.slug == slug
    ).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
        if counter > 1000:
            raise ValueError("Unable to generate unique slug")
    
    db_tab = models.CustomTab(
        user_id=user_id,
        name=tab.name,
        slug=slug,
        source_type=tab.source_type,
        allow_uploads=tab.allow_uploads
    )
    db.add(db_tab)
    db.flush()
    
    for order, field_data in enumerate(tab.fields):
        db_field = models.CustomTabField(
            tab_id=db_tab.id,
            key=field_data.key,
            label=field_data.label,
            field_type=field_data.field_type,
            required=field_data.required,
            order=order
        )
        db.add(db_field)
    
    db.commit()
    db.refresh(db_tab)
    return db_tab


def update_custom_tab(
    db: Session,
    user_id: int,
    tab_id: int,
    tab_update: schemas.CustomTabUpdate
) -> Optional[models.CustomTab]:
    db_tab = get_custom_tab_by_id(db, user_id, tab_id)
    if db_tab is None:
        return None
    
    update_dict = tab_update.dict(exclude_unset=True)
    
    if "fields" in update_dict:
        if len(update_dict["fields"]) > MAX_FIELDS_PER_TAB:
            raise ValueError(f"Maximum of {MAX_FIELDS_PER_TAB} fields allowed per tab")
        
        field_keys = [f["key"] for f in update_dict["fields"]]
        if len(field_keys) != len(set(field_keys)):
            raise ValueError("Duplicate field keys are not allowed")
        
        for field_data in update_dict["fields"]:
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', field_data["key"]):
                raise ValueError(f"Field key '{field_data['key']}' must start with a letter or underscore and contain only alphanumeric characters and underscores")
        
        valid_field_types = ('text', 'number', 'date', 'boolean', 'rating', 'review', 'status')
        for field_data in update_dict["fields"]:
            if field_data["field_type"] not in valid_field_types:
                raise ValueError(f"Invalid field_type '{field_data['field_type']}'. Must be one of: {', '.join(valid_field_types)}")
    
    if "source_type" in update_dict:
        if update_dict["source_type"] not in ('none', 'omdb', 'jikan', 'rawg'):
            raise ValueError("source_type must be one of: none, omdb, jikan, rawg")
    
    if "name" in update_dict:
        db_tab.name = update_dict["name"]
        base_slug = _generate_slug(update_dict["name"])
        slug = base_slug
        counter = 1
        
        while db.query(models.CustomTab).filter(
            models.CustomTab.user_id == user_id,
            models.CustomTab.slug == slug,
            models.CustomTab.id != tab_id
        ).first():
            slug = f"{base_slug}-{counter}"
            counter += 1
            if counter > 1000:
                raise ValueError("Unable to generate unique slug")
        db_tab.slug = slug
    
    if "source_type" in update_dict:
        db_tab.source_type = update_dict["source_type"]
    
    if "allow_uploads" in update_dict:
        db_tab.allow_uploads = update_dict["allow_uploads"]
    
    if "fields" in update_dict:
        db.query(models.CustomTabField).filter(
            models.CustomTabField.tab_id == tab_id
        ).delete()
        
        for order, field_data in enumerate(update_dict["fields"]):
            db_field = models.CustomTabField(
                tab_id=tab_id,
                key=field_data["key"],
                label=field_data["label"],
                field_type=field_data["field_type"],
                required=field_data.get("required", False),
                order=order
            )
            db.add(db_field)
    
    db.commit()
    db.refresh(db_tab)
    return db_tab


def delete_custom_tab(db: Session, user_id: int, tab_id: int) -> Optional[models.CustomTab]:
    db_tab = get_custom_tab_by_id(db, user_id, tab_id)
    if db_tab is None:
        return None
    db.delete(db_tab)
    db.commit()
    return db_tab


def get_custom_tab_items(
    db: Session,
    user_id: int,
    tab_id: int,
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    order: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> List[models.CustomTabItem]:
    tab = get_custom_tab_by_id(db, user_id, tab_id)
    if tab is None:
        return []
    
    query = db.query(models.CustomTabItem).filter(models.CustomTabItem.tab_id == tab_id)
    
    if search:
        like_pattern = f"%{search}%"
        query = query.filter(models.CustomTabItem.title.ilike(like_pattern))
    
    sort_order = asc
    if order and order.lower() == "desc":
        sort_order = desc
    
    if sort_by == "title":
        query = query.order_by(sort_order(models.CustomTabItem.title))
    elif sort_by == "created_at":
        query = query.order_by(sort_order(models.CustomTabItem.created_at))
    else:
        query = query.order_by(desc(models.CustomTabItem.created_at))
    
    if offset:
        query = query.offset(offset)
    if limit:
        query = query.limit(limit)
    
    return query.all()


def get_custom_tab_item_by_id(
    db: Session,
    user_id: int,
    tab_id: int,
    item_id: int
) -> Optional[models.CustomTabItem]:
    tab = get_custom_tab_by_id(db, user_id, tab_id)
    if tab is None:
        return None
    
    return db.query(models.CustomTabItem).filter(
        models.CustomTabItem.id == item_id,
        models.CustomTabItem.tab_id == tab_id
    ).first()


def _validate_field_values(
    db: Session,
    tab_id: int,
    field_values: dict
) -> tuple[bool, Optional[str]]:
    if not isinstance(field_values, dict):
        return False, "field_values must be a dictionary"
    
    fields = db.query(models.CustomTabField).filter(
        models.CustomTabField.tab_id == tab_id
    ).order_by(models.CustomTabField.order).all()
    
    field_dict = {f.key: f for f in fields}
    
    for key in field_values:
        if key not in field_dict:
            return False, f"Unknown field key: '{key}'"
    
    for field in fields:
        if field.required and (field.key not in field_values or field_values[field.key] is None or field_values[field.key] == ""):
            return False, f"Required field '{field.label}' is missing or empty"
        
        if field.key in field_values:
            value = field_values[field.key]
            
            if value is None or value == "":
                continue
            
            if field.field_type == "number":
                try:
                    num_value = float(value)
                    if not (-1e10 <= num_value <= 1e10):
                        return False, f"Field '{field.label}' value is out of range"
                except (ValueError, TypeError):
                    return False, f"Field '{field.label}' must be a number"
            
            if field.field_type == "rating":
                try:
                    rating = float(value)
                    if rating < 0 or rating > 10:
                        return False, f"Field '{field.label}' must be between 0 and 10"
                    if len(str(rating).split('.')[-1]) > 1:
                        return False, f"Field '{field.label}' must have at most one decimal place"
                except (ValueError, TypeError):
                    return False, f"Field '{field.label}' must be a valid rating"
            
            if field.field_type == "date":
                if not isinstance(value, str):
                    return False, f"Field '{field.label}' must be a date string (YYYY-MM-DD)"
                try:
                    from datetime import datetime
                    datetime.strptime(value, "%Y-%m-%d")
                except ValueError:
                    return False, f"Field '{field.label}' must be a valid date in YYYY-MM-DD format"
            
            if field.field_type == "boolean":
                if not isinstance(value, bool) and value not in ("true", "false", "True", "False", "0", "1", 0, 1, ""):
                    return False, f"Field '{field.label}' must be a boolean"
            
            if field.field_type == "text" and isinstance(value, str) and len(value) > 10000:
                return False, f"Field '{field.label}' text is too long (max 10000 characters)"
            
            if field.field_type == "review" and isinstance(value, str) and len(value) > 50000:
                return False, f"Field '{field.label}' review is too long (max 50000 characters)"
    
    return True, None


def create_custom_tab_item(
    db: Session,
    user_id: int,
    tab_id: int,
    item: schemas.CustomTabItemCreate
) -> tuple[Optional[models.CustomTabItem], Optional[str]]:
    tab = get_custom_tab_by_id(db, user_id, tab_id)
    if tab is None:
        return None, "Custom tab not found"
    
    items_count = db.query(models.CustomTabItem).filter(
        models.CustomTabItem.tab_id == tab_id
    ).count()
    
    if items_count >= MAX_ITEMS_PER_TAB:
        return None, f"Maximum of {MAX_ITEMS_PER_TAB} items allowed per tab"
    
    if not item.title or not item.title.strip():
        return None, "Title is required and cannot be empty"
    
    if len(item.title) > 500:
        return None, "Title is too long (max 500 characters)"
    
    is_valid, error_msg = _validate_field_values(db, tab_id, item.field_values)
    if not is_valid:
        return None, error_msg
    
    if item.poster_url and len(item.poster_url) > 2000:
        return None, "Poster URL is too long (max 2000 characters)"
    
    field_values_json = json.dumps(item.field_values) if item.field_values else None
    
    db_item = models.CustomTabItem(
        tab_id=tab_id,
        title=item.title,
        field_values=field_values_json,
        poster_url=item.poster_url
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item, None


def update_custom_tab_item(
    db: Session,
    user_id: int,
    tab_id: int,
    item_id: int,
    item_update: schemas.CustomTabItemUpdate
) -> tuple[Optional[models.CustomTabItem], Optional[str]]:
    db_item = get_custom_tab_item_by_id(db, user_id, tab_id, item_id)
    if db_item is None:
        return None, "Custom tab item not found"
    
    update_dict = item_update.dict(exclude_unset=True)
    
    if "title" in update_dict:
        if not update_dict["title"] or not update_dict["title"].strip():
            return None, "Title is required and cannot be empty"
        if len(update_dict["title"]) > 500:
            return None, "Title is too long (max 500 characters)"
    
    if "poster_url" in update_dict and update_dict["poster_url"]:
        if len(update_dict["poster_url"]) > 2000:
            return None, "Poster URL is too long (max 2000 characters)"
    
    if "field_values" in update_dict:
        is_valid, error_msg = _validate_field_values(db, tab_id, update_dict["field_values"])
        if not is_valid:
            return None, error_msg
        update_dict["field_values"] = json.dumps(update_dict["field_values"]) if update_dict["field_values"] else None
    
    for field, value in update_dict.items():
        setattr(db_item, field, value)
    
    db.commit()
    db.refresh(db_item)
    return db_item, None


def delete_custom_tab_item(
    db: Session,
    user_id: int,
    tab_id: int,
    item_id: int
) -> Optional[models.CustomTabItem]:
    db_item = get_custom_tab_item_by_id(db, user_id, tab_id, item_id)
    if db_item is None:
        return None
    db.delete(db_item)
    db.commit()
    return db_item


def update_custom_tab_item_poster(
    db: Session,
    user_id: int,
    tab_id: int,
    item_id: int,
    poster_url: str,
    poster_data: bytes = None,
    poster_mime_type: str = None
) -> Optional[models.CustomTabItem]:
    db_item = get_custom_tab_item_by_id(db, user_id, tab_id, item_id)
    if db_item is None:
        return None
    
    db_item.poster_url = poster_url
    if poster_data is not None:
        db_item.poster_data = poster_data
    if poster_mime_type is not None:
        db_item.poster_mime_type = poster_mime_type
    
    db.commit()
    db.refresh(db_item)
    return db_item
