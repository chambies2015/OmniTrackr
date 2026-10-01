"""Recommendation Postcards: expiring, owner-controlled recommendation prompts."""
import secrets
from datetime import datetime, timedelta
from typing import Dict, Tuple, Type

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..dependencies import get_current_user, get_db

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

CategoryDetails = Tuple[Type, str, str]
CATEGORIES: Dict[str, CategoryDetails] = {
    "movies": (models.Movie, "Movie", "watched"),
    "tv-shows": (models.TVShow, "TV show", "watched"),
    "anime": (models.Anime, "Anime", "watched"),
    "video-games": (models.VideoGame, "Game", "played"),
    "music": (models.Music, "Album", "listened"),
    "books": (models.Book, "Book", "read"),
}
MAX_OPEN_POSTCARDS = 5


def _categories(postcard: models.RecommendationRequest) -> list[str]:
    return [value for value in postcard.allowed_categories.split(",") if value in CATEGORIES]


def _submission_count(postcard: models.RecommendationRequest) -> int:
    return len(postcard.submissions)


def _state(postcard: models.RecommendationRequest) -> str:
    if postcard.status != "open":
        return "closed"
    if postcard.expires_at <= datetime.utcnow():
        return "expired"
    if _submission_count(postcard) >= postcard.max_responses:
        return "full"
    return "open"


def _public_postcard(postcard: models.RecommendationRequest) -> dict:
    count = _submission_count(postcard)
    categories = _categories(postcard)
    return {
        "owner_username": postcard.owner.username,
        "prompt": postcard.prompt,
        "categories": [
            {"value": category, "label": CATEGORIES[category][1]}
            for category in categories
        ],
        "max_responses": postcard.max_responses,
        "response_count": count,
        "remaining": max(0, postcard.max_responses - count),
        "state": _state(postcard),
        "expires_at": postcard.expires_at,
    }


def _owner_postcard(postcard: models.RecommendationRequest) -> dict:
    result = _public_postcard(postcard)
    result.update({
        "id": postcard.id,
        "share_path": f"/recommend/{postcard.public_token}",
        "created_at": postcard.created_at,
        "invitation_count": len(postcard.invitations),
    })
    return result


def _serialize_submission(entry: models.RecommendationSubmission) -> dict:
    return {
        "id": entry.id,
        "request_id": entry.request_id,
        "prompt": entry.request.prompt,
        "guest_name": entry.guest_name,
        "category": entry.category,
        "category_label": CATEGORIES[entry.category][1],
        "title": entry.title,
        "reason": entry.reason,
        "status": entry.status,
        "accepted_item_id": entry.accepted_item_id,
        "created_at": entry.created_at,
    }


def _get_by_token(db: Session, token: str, lock: bool = False) -> models.RecommendationRequest:
    query = db.query(models.RecommendationRequest).filter(
        models.RecommendationRequest.public_token == token,
    )
    if lock:
        query = query.with_for_update()
    postcard = query.first()
    if not postcard:
        raise HTTPException(status_code=404, detail="Recommendation Postcard not found")
    return postcard


def _get_owned(db: Session, owner_id: int, request_id: int) -> models.RecommendationRequest:
    postcard = db.query(models.RecommendationRequest).filter(
        models.RecommendationRequest.id == request_id,
        models.RecommendationRequest.owner_id == owner_id,
    ).first()
    if not postcard:
        raise HTTPException(status_code=404, detail="Recommendation Postcard not found")
    return postcard


def _require_open(postcard: models.RecommendationRequest) -> None:
    current_state = _state(postcard)
    if current_state == "expired":
        raise HTTPException(status_code=410, detail="This Recommendation Postcard has expired")
    if current_state == "closed":
        raise HTTPException(status_code=409, detail="This Recommendation Postcard is closed")
    if current_state == "full":
        raise HTTPException(status_code=409, detail="This Recommendation Postcard is full")


def _validate_suggestion(postcard: models.RecommendationRequest, category: str, title: str, db: Session) -> None:
    if category not in _categories(postcard):
        raise HTTPException(status_code=400, detail="That media type is not invited on this postcard")
    duplicate = db.query(models.RecommendationSubmission).filter(
        models.RecommendationSubmission.request_id == postcard.id,
        models.RecommendationSubmission.category == category,
        func.lower(func.trim(models.RecommendationSubmission.title)) == title.strip().lower(),
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="That title was already recommended on this postcard")


def _add_submission(
    db: Session,
    postcard: models.RecommendationRequest,
    guest_name: str,
    category: str,
    title: str,
    reason: str,
    recommender_user_id: int | None = None,
) -> models.RecommendationSubmission:
    _require_open(postcard)
    _validate_suggestion(postcard, category, title, db)
    entry = models.RecommendationSubmission(
        request_id=postcard.id,
        recommender_user_id=recommender_user_id,
        guest_name=guest_name,
        category=category,
        title=title,
        reason=reason,
    )
    db.add(entry)
    db.add(models.Notification(
        user_id=postcard.owner_id,
        type="recommendation_received",
        message=f"{guest_name} recommended {title} for your postcard.",
    ))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="That recommendation could not be added twice")
    db.refresh(entry)
    return entry


@router.post("/requests/", status_code=status.HTTP_201_CREATED)
async def create_request(
    payload: schemas.RecommendationRequestCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    open_count = db.query(func.count(models.RecommendationRequest.id)).filter(
        models.RecommendationRequest.owner_id == current_user.id,
        models.RecommendationRequest.status == "open",
        models.RecommendationRequest.expires_at > datetime.utcnow(),
    ).scalar() or 0
    if open_count >= MAX_OPEN_POSTCARDS:
        raise HTTPException(
            status_code=409,
            detail="Close an open postcard before creating another (maximum 5)",
        )
    postcard = models.RecommendationRequest(
        owner_id=current_user.id,
        public_token=secrets.token_urlsafe(24),
        prompt=payload.prompt,
        allowed_categories=",".join(payload.categories),
        max_responses=payload.max_responses,
        expires_at=datetime.utcnow() + timedelta(days=payload.expires_in_days),
    )
    db.add(postcard)
    db.commit()
    db.refresh(postcard)
    return _owner_postcard(postcard)


@router.get("/requests/")
async def list_requests(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    postcards = db.query(models.RecommendationRequest).filter(
        models.RecommendationRequest.owner_id == current_user.id,
    ).order_by(models.RecommendationRequest.created_at.desc(), models.RecommendationRequest.id.desc()).all()
    return [_owner_postcard(postcard) for postcard in postcards]


@router.post("/requests/{request_id}/close")
async def close_request(
    request_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    postcard = _get_owned(db, current_user.id, request_id)
    postcard.status = "closed"
    db.commit()
    return _owner_postcard(postcard)


@router.post("/requests/{request_id}/invite", status_code=status.HTTP_201_CREATED)
async def invite_friend(
    request_id: int,
    payload: schemas.RecommendationInviteCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    postcard = _get_owned(db, current_user.id, request_id)
    _require_open(postcard)
    if not crud.are_friends(db, current_user.id, payload.friend_id):
        raise HTTPException(status_code=403, detail="You can only invite an existing friend")
    invitation = models.RecommendationInvitation(request_id=postcard.id, recipient_id=payload.friend_id)
    db.add(invitation)
    db.add(models.Notification(
        user_id=payload.friend_id,
        type="recommendation_invitation",
        message=f"{current_user.username} sent you a Recommendation Postcard.",
    ))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="That friend is already invited")
    return {"message": "Invitation sent", "friend_id": payload.friend_id}


@router.get("/invitations/")
async def list_invitations(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    invitations = db.query(models.RecommendationInvitation).filter(
        models.RecommendationInvitation.recipient_id == current_user.id,
    ).order_by(models.RecommendationInvitation.created_at.desc()).all()
    result = []
    for invitation in invitations:
        postcard = invitation.request
        if _state(postcard) != "open":
            continue
        responded = db.query(models.RecommendationSubmission.id).filter(
            models.RecommendationSubmission.request_id == postcard.id,
            models.RecommendationSubmission.recommender_user_id == current_user.id,
        ).first() is not None
        result.append({
            "request_id": postcard.id,
            "sender_username": postcard.owner.username,
            "prompt": postcard.prompt,
            "categories": _public_postcard(postcard)["categories"],
            "expires_at": postcard.expires_at,
            "responded": responded,
        })
    return result


@router.post("/requests/{request_id}/respond", status_code=status.HTTP_201_CREATED)
async def respond_as_friend(
    request_id: int,
    payload: schemas.RecommendationFriendSubmissionCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    invitation = db.query(models.RecommendationInvitation).filter(
        models.RecommendationInvitation.request_id == request_id,
        models.RecommendationInvitation.recipient_id == current_user.id,
    ).first()
    if not invitation:
        raise HTTPException(status_code=403, detail="This postcard was not sent to you")
    if not crud.are_friends(db, current_user.id, invitation.request.owner_id):
        raise HTTPException(status_code=403, detail="This postcard invitation is no longer available")
    existing_response = db.query(models.RecommendationSubmission.id).filter(
        models.RecommendationSubmission.request_id == request_id,
        models.RecommendationSubmission.recommender_user_id == current_user.id,
    ).first()
    if existing_response:
        raise HTTPException(status_code=409, detail="You already answered this postcard")
    postcard = db.query(models.RecommendationRequest).filter(
        models.RecommendationRequest.id == request_id,
    ).with_for_update().first()
    entry = _add_submission(
        db, postcard, current_user.username, payload.category,
        payload.title, payload.reason, current_user.id,
    )
    return {"message": "Recommendation delivered", "id": entry.id}


@router.get("/inbox/")
async def list_inbox(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entries = db.query(models.RecommendationSubmission).join(models.RecommendationRequest).filter(
        models.RecommendationRequest.owner_id == current_user.id,
    ).order_by(
        models.RecommendationSubmission.status.desc(),
        models.RecommendationSubmission.created_at.desc(),
    ).all()
    return [_serialize_submission(entry) for entry in entries]


def _library_item(db: Session, user_id: int, category: str, title: str):
    model, _, _ = CATEGORIES[category]
    return db.query(model).filter(
        model.user_id == user_id,
        func.lower(func.trim(model.title)) == title.strip().lower(),
    ).first()


def _new_library_item(user_id: int, category: str, title: str):
    common = {"user_id": user_id, "title": title, "review_public": False}
    if category == "movies":
        return models.Movie(**common, director="Unknown director", watched=False)
    if category == "tv-shows":
        return models.TVShow(**common, watched=False)
    if category == "anime":
        return models.Anime(**common, watched=False)
    if category == "video-games":
        return models.VideoGame(**common, played=False)
    if category == "music":
        return models.Music(**common, artist="Unknown artist", listened=False)
    return models.Book(**common, author="Unknown author", read=False)


@router.post("/submissions/{submission_id}/triage")
async def triage_submission(
    submission_id: int,
    payload: schemas.RecommendationTriage,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry = db.query(models.RecommendationSubmission).join(models.RecommendationRequest).filter(
        models.RecommendationSubmission.id == submission_id,
        models.RecommendationRequest.owner_id == current_user.id,
    ).with_for_update().first()
    if not entry:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    if entry.status == "accepted":
        raise HTTPException(status_code=409, detail="That recommendation is already in your library")

    if payload.action in {"save", "dismiss"}:
        entry.status = "saved" if payload.action == "save" else "dismissed"
        db.commit()
        return {"status": entry.status, "library_changed": False}

    item = _library_item(db, current_user.id, entry.category, entry.title)
    created = item is None
    if item is None:
        item = _new_library_item(current_user.id, entry.category, entry.title)
        db.add(item)
        db.flush()

    queued = False
    if payload.action == "next-up":
        _, _, completion_field = CATEGORIES[entry.category]
        if not bool(getattr(item, completion_field)):
            existing_queue = db.query(models.NextUpItem).filter(
                models.NextUpItem.user_id == current_user.id,
                models.NextUpItem.category == entry.category,
                models.NextUpItem.item_id == item.id,
            ).first()
            if not existing_queue:
                highest = db.query(func.max(models.NextUpItem.position)).filter(
                    models.NextUpItem.user_id == current_user.id,
                ).scalar()
                db.add(models.NextUpItem(
                    user_id=current_user.id,
                    category=entry.category,
                    item_id=item.id,
                    position=(highest if highest is not None else -1) + 1,
                ))
                queued = True

    entry.status = "accepted"
    entry.accepted_item_id = item.id
    db.commit()
    return {
        "status": entry.status,
        "library_changed": created,
        "item_id": item.id,
        "queued": queued,
    }


@router.get("/public/{token}")
async def get_public_request(token: str, db: Session = Depends(get_db)):
    return _public_postcard(_get_by_token(db, token))


@router.post("/public/{token}", status_code=status.HTTP_201_CREATED)
async def submit_public_recommendation(
    token: str,
    payload: schemas.RecommendationSubmissionCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    # A filled invisible field indicates a basic form bot. Respond generically so
    # the trap cannot be tuned, while storing nothing and notifying nobody.
    if payload.website:
        return {"message": "Thanks — your recommendation was received."}
    postcard = _get_by_token(db, token, lock=True)
    entry = _add_submission(
        db, postcard, payload.guest_name, payload.category, payload.title, payload.reason,
    )
    return {"message": "Thanks — your recommendation was delivered.", "id": entry.id}
