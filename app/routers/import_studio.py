"""Preview-first, additive CSV migration endpoints."""
import json
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import models
from ..dependencies import get_current_user, get_db
from ..import_studio import MAX_IMPORT_BYTES, apply_classified, classify_rows, fingerprint, parse_csv, summarize


router = APIRouter(prefix="/import-studio", tags=["import-studio"])


async def _read_upload(file: UploadFile) -> bytes:
    if not file.filename or not file.filename.lower().endswith((".csv", ".tsv")):
        raise HTTPException(status_code=400, detail="Choose a CSV or TSV file.")
    content = await file.read(MAX_IMPORT_BYTES + 1)
    if not content:
        raise HTTPException(status_code=400, detail="The selected file is empty.")
    return content


def _mapping_or_400(mapping_json: str) -> dict[str, str]:
    if not mapping_json:
        return {}
    try:
        value = json.loads(mapping_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Column mapping must be valid JSON.") from exc
    if not isinstance(value, dict) or not all(isinstance(key, str) and isinstance(item, str) for key, item in value.items()):
        raise HTTPException(status_code=400, detail="Column mapping must pair field names with CSV columns.")
    return value


def _parse_or_400(content: bytes, source: str, category: str | None, mapping: dict[str, str]):
    try:
        return parse_csv(content, source, category, mapping)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/preview/")
async def preview_import(
    file: UploadFile = File(...),
    source: str = Form("auto"),
    category: str | None = Form(None),
    mapping_json: str = Form(""),
    status_filter: Literal["all", "ready", "duplicate", "invalid"] = Form("all"),
    offset: int = Form(0, ge=0),
    limit: int = Form(100, ge=1, le=100),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Parse a migration file and report every outcome without writing data."""
    content = await _read_upload(file)
    mapping = _mapping_or_400(mapping_json)
    detected, rows = _parse_or_400(content, source, category, mapping)
    digest = fingerprint(content, source, category or "", mapping_json)
    return summarize(detected, digest, classify_rows(db, current_user.id, rows), status_filter, offset, limit)


@router.post("/apply/")
async def apply_import(
    file: UploadFile = File(...),
    fingerprint_confirmation: str = Form(...),
    source: str = Form("auto"),
    category: str | None = Form(None),
    mapping_json: str = Form(""),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Atomically create only the rows that a matching preview marked ready."""
    content = await _read_upload(file)
    digest = fingerprint(content, source, category or "", mapping_json)
    if digest != fingerprint_confirmation:
        raise HTTPException(status_code=409, detail="The file changed after preview. Preview it again before importing.")
    mapping = _mapping_or_400(mapping_json)
    detected, rows = _parse_or_400(content, source, category, mapping)
    try:
        # Serialize confirmed imports for this account in production PostgreSQL.
        # Reclassify after the lock: another completed import may add duplicates.
        db.query(models.User).filter(models.User.id == current_user.id).with_for_update().one()
        classified = classify_rows(db, current_user.id, rows)
        result = apply_classified(db, current_user.id, classified)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Nothing was imported because the batch could not be saved.") from exc
    return {**result, "detected_source": detected}


@router.get("/template/{category}/")
async def download_template(
    category: str,
    current_user: models.User = Depends(get_current_user),
):
    """Download a safe generic CSV starter for one built-in media category."""
    normalized = category.strip().lower()
    if normalized not in {"movies", "tv-shows", "anime", "video-games", "music", "books"}:
        raise HTTPException(status_code=404, detail="Unknown media category.")
    columns = {
        "movies": "title,director,year,rating,watched,review\n",
        "tv-shows": "title,year,seasons,episodes,rating,watched,review\n",
        "anime": "title,year,seasons,episodes,rating,watched,review\n",
        "video-games": "title,release_date,genre,rating,played,review\n",
        "music": "title,artist,year,genre,rating,listened,review\n",
        "books": "title,author,year,genre,rating,read,review\n",
    }
    filename = f"omnitrackr-{normalized}-template.csv"
    return Response(
        content=columns[normalized],
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
