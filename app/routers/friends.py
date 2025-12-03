"""
Friends endpoints for the OmniTrackr API.
"""
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_

from .. import crud, schemas, models
from ..dependencies import get_db, get_current_user

router = APIRouter(prefix="/friends", tags=["friends"])


@router.post("/request", response_model=schemas.FriendRequestResponse)
async def send_friend_request(
    request_data: schemas.FriendRequestCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send a friend request to another user by username."""
    # Find the receiver by username
    receiver = crud.get_user_by_username(db, request_data.receiver_username)
    if not receiver:
        raise HTTPException(status_code=404, detail="User not found")
    
    if receiver.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot send friend request to yourself")
    
    try:
        friend_request = crud.create_friend_request(db, current_user.id, receiver.id)
        # Refresh to load relationships
        db.refresh(friend_request)
        return friend_request
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/requests", response_model=dict)
async def get_friend_requests(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get pending friend requests (sent and received)."""
    sent, received = crud.get_friend_requests_by_user(db, current_user.id)
    
    return {
        "sent": [schemas.FriendRequestResponse.model_validate(req) for req in sent],
        "received": [schemas.FriendRequestResponse.model_validate(req) for req in received]
    }


@router.post("/requests/{request_id}/accept", response_model=schemas.FriendRequestResponse)
async def accept_friend_request(
    request_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Accept a friend request."""
    try:
        friend_request = crud.accept_friend_request(db, request_id, current_user.id)
        if not friend_request:
            raise HTTPException(status_code=404, detail="Friend request not found")
        db.refresh(friend_request)
        return friend_request
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/requests/{request_id}/deny", response_model=schemas.FriendRequestResponse)
async def deny_friend_request(
    request_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Deny a friend request."""
    try:
        friend_request = crud.deny_friend_request(db, request_id, current_user.id)
        if not friend_request:
            raise HTTPException(status_code=404, detail="Friend request not found")
        db.refresh(friend_request)
        return friend_request
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/requests/{request_id}", response_model=dict)
async def cancel_friend_request(
    request_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel a sent friend request."""
    try:
        friend_request = crud.cancel_friend_request(db, request_id, current_user.id)
        if not friend_request:
            raise HTTPException(status_code=404, detail="Friend request not found")
        return {"message": "Friend request cancelled"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[schemas.FriendshipResponse])
async def get_friends(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of all friends."""
    friends = crud.get_friends(db, current_user.id)
    
    # Convert to FriendshipResponse format
    friendships = []
    for friend in friends:
        # Find the friendship record
        user1_id = min(current_user.id, friend.id)
        user2_id = max(current_user.id, friend.id)
        friendship = db.query(models.Friendship).filter(
            and_(
                models.Friendship.user1_id == user1_id,
                models.Friendship.user2_id == user2_id
            )
        ).first()
        if friendship:
            friendships.append(schemas.FriendshipResponse(
                id=friendship.id,
                friend=friend,
                created_at=friendship.created_at
            ))
    
    return friendships


@router.delete("/{friend_id}", response_model=dict)
async def unfriend_user(
    friend_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Unfriend a user."""
    success = crud.remove_friendship(db, current_user.id, friend_id)
    if not success:
        raise HTTPException(status_code=404, detail="Friendship not found")
    return {"message": "Unfriended successfully"}


@router.get("/{friend_id}/profile", response_model=schemas.FriendProfileSummary)
async def get_friend_profile(
    friend_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get friend's profile summary (counts only, respects privacy)."""
    # Verify friendship
    if not crud.are_friends(db, current_user.id, friend_id):
        raise HTTPException(status_code=403, detail="You are not friends with this user")
    
    profile = crud.get_friend_profile_summary(db, friend_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Friend not found")
    
    return profile


@router.get("/{friend_id}/movies", response_model=schemas.FriendMoviesResponse)
async def get_friend_movies(
    friend_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get friend's movies list (if not private, requires friendship)."""
    # Verify friendship
    if not crud.are_friends(db, current_user.id, friend_id):
        raise HTTPException(status_code=403, detail="You are not friends with this user")
    
    movies = crud.get_friend_movies(db, friend_id)
    if movies is None:
        # Check if friend exists
        friend = crud.get_user_by_id(db, friend_id)
        if friend is None:
            raise HTTPException(status_code=404, detail="Friend not found")
        # Data is private
        raise HTTPException(status_code=403, detail="This user has made their movies private")
    
    return schemas.FriendMoviesResponse(movies=movies, count=len(movies))


@router.get("/{friend_id}/tv-shows", response_model=schemas.FriendTVShowsResponse)
async def get_friend_tv_shows(
    friend_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get friend's TV shows list (if not private, requires friendship)."""
    # Verify friendship
    if not crud.are_friends(db, current_user.id, friend_id):
        raise HTTPException(status_code=403, detail="You are not friends with this user")
    
    tv_shows = crud.get_friend_tv_shows(db, friend_id)
    if tv_shows is None:
        # Check if friend exists
        friend = crud.get_user_by_id(db, friend_id)
        if friend is None:
            raise HTTPException(status_code=404, detail="Friend not found")
        # Data is private
        raise HTTPException(status_code=403, detail="This user has made their TV shows private")
    
    return schemas.FriendTVShowsResponse(tv_shows=tv_shows, count=len(tv_shows))


@router.get("/{friend_id}/anime", response_model=schemas.FriendAnimeResponse)
async def get_friend_anime(
    friend_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get friend's anime list (if not private, requires friendship)."""
    # Verify friendship
    if not crud.are_friends(db, current_user.id, friend_id):
        raise HTTPException(status_code=403, detail="You are not friends with this user")
    
    anime = crud.get_friend_anime(db, friend_id)
    if anime is None:
        # Check if friend exists
        friend = crud.get_user_by_id(db, friend_id)
        if friend is None:
            raise HTTPException(status_code=404, detail="Friend not found")
        # Data is private
        raise HTTPException(status_code=403, detail="This user has made their anime private")
    
    return schemas.FriendAnimeResponse(anime=anime, count=len(anime))


@router.get("/{friend_id}/video-games", response_model=schemas.FriendVideoGamesResponse)
async def get_friend_video_games(
    friend_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get friend's video games list (if not private, requires friendship)."""
    # Verify friendship
    if not crud.are_friends(db, current_user.id, friend_id):
        raise HTTPException(status_code=403, detail="You are not friends with this user")
    
    video_games = crud.get_friend_video_games(db, friend_id)
    if video_games is None:
        # Check if friend exists
        friend = crud.get_user_by_id(db, friend_id)
        if friend is None:
            raise HTTPException(status_code=404, detail="Friend not found")
        # Data is private
        raise HTTPException(status_code=403, detail="This user has made their video games private")
    
    return schemas.FriendVideoGamesResponse(video_games=video_games, count=len(video_games))


@router.get("/{friend_id}/statistics", response_model=schemas.FriendStatisticsResponse)
async def get_friend_statistics(
    friend_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get friend's statistics (if not private, requires friendship, compact format)."""
    # Verify friendship
    if not crud.are_friends(db, current_user.id, friend_id):
        raise HTTPException(status_code=403, detail="You are not friends with this user")
    
    stats = crud.get_friend_statistics(db, friend_id)
    if stats is None:
        # Check if friend exists
        friend = crud.get_user_by_id(db, friend_id)
        if friend is None:
            raise HTTPException(status_code=404, detail="Friend not found")
        # Data is private
        raise HTTPException(status_code=403, detail="This user has made their statistics private")
    
    return schemas.FriendStatisticsResponse(
        watch_stats=schemas.WatchStatistics(**stats["watch_stats"]),
        rating_stats=schemas.RatingStatistics(**stats["rating_stats"]),
        generated_at=datetime.now().isoformat()
    )

