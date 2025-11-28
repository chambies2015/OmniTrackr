"""
Tests for friends and notifications features.
"""
import pytest
from datetime import datetime, timedelta
from app import crud, schemas, auth, models
from fastapi import HTTPException


class TestFriendRequestCRUD:
    """Test friend request CRUD operations."""
    
    def test_create_friend_request(self, db_session, test_user_data):
        """Test creating a friend request."""
        # Create two users
        user1_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user1 = crud.create_user(db_session, user1_create, hashed_password)
        
        user_data2 = test_user_data.copy()
        user_data2["email"] = "user2@example.com"
        user_data2["username"] = "user2"
        user2_create = schemas.UserCreate(**user_data2)
        user2 = crud.create_user(db_session, user2_create, hashed_password)
        
        # Create friend request
        friend_request = crud.create_friend_request(db_session, user1.id, user2.id)
        
        assert friend_request is not None
        assert friend_request.sender_id == user1.id
        assert friend_request.receiver_id == user2.id
        assert friend_request.status == "pending"
        assert friend_request.expires_at > datetime.utcnow()
        
        # Check notification was created
        notifications = crud.get_notifications(db_session, user2.id)
        assert len(notifications) == 1
        assert notifications[0].type == "friend_request_received"
        assert user1.username in notifications[0].message
    
    def test_create_friend_request_already_friends(self, db_session, test_user_data):
        """Test creating friend request when users are already friends."""
        # Create two users
        user1_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user1 = crud.create_user(db_session, user1_create, hashed_password)
        
        user_data2 = test_user_data.copy()
        user_data2["email"] = "user2@example.com"
        user_data2["username"] = "user2"
        user2_create = schemas.UserCreate(**user_data2)
        user2 = crud.create_user(db_session, user2_create, hashed_password)
        
        # Create friendship first
        user1_id = min(user1.id, user2.id)
        user2_id = max(user1.id, user2.id)
        crud.create_friendship(db_session, user1_id, user2_id)
        
        # Try to create friend request
        with pytest.raises(ValueError, match="already friends"):
            crud.create_friend_request(db_session, user1.id, user2.id)
    
    def test_create_friend_request_duplicate(self, db_session, test_user_data):
        """Test creating duplicate friend request."""
        # Create two users
        user1_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user1 = crud.create_user(db_session, user1_create, hashed_password)
        
        user_data2 = test_user_data.copy()
        user_data2["email"] = "user2@example.com"
        user_data2["username"] = "user2"
        user2_create = schemas.UserCreate(**user_data2)
        user2 = crud.create_user(db_session, user2_create, hashed_password)
        
        # Create first friend request
        crud.create_friend_request(db_session, user1.id, user2.id)
        
        # Try to create duplicate
        with pytest.raises(ValueError, match="already exists"):
            crud.create_friend_request(db_session, user1.id, user2.id)
    
    def test_get_friend_requests_by_user(self, db_session, test_user_data):
        """Test getting friend requests for a user."""
        # Create three users
        user1_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user1 = crud.create_user(db_session, user1_create, hashed_password)
        
        user_data2 = test_user_data.copy()
        user_data2["email"] = "user2@example.com"
        user_data2["username"] = "user2"
        user2_create = schemas.UserCreate(**user_data2)
        user2 = crud.create_user(db_session, user2_create, hashed_password)
        
        user_data3 = test_user_data.copy()
        user_data3["email"] = "user3@example.com"
        user_data3["username"] = "user3"
        user3_create = schemas.UserCreate(**user_data3)
        user3 = crud.create_user(db_session, user3_create, hashed_password)
        
        # User1 sends request to user2
        crud.create_friend_request(db_session, user1.id, user2.id)
        # User3 sends request to user1
        crud.create_friend_request(db_session, user3.id, user1.id)
        
        # Get requests for user1
        sent, received = crud.get_friend_requests_by_user(db_session, user1.id)
        
        assert len(sent) == 1
        assert sent[0].receiver_id == user2.id
        assert len(received) == 1
        assert received[0].sender_id == user3.id
    
    def test_accept_friend_request(self, db_session, test_user_data):
        """Test accepting a friend request."""
        # Create two users
        user1_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user1 = crud.create_user(db_session, user1_create, hashed_password)
        
        user_data2 = test_user_data.copy()
        user_data2["email"] = "user2@example.com"
        user_data2["username"] = "user2"
        user2_create = schemas.UserCreate(**user_data2)
        user2 = crud.create_user(db_session, user2_create, hashed_password)
        
        # Create friend request
        friend_request = crud.create_friend_request(db_session, user1.id, user2.id)
        
        # Accept request
        accepted = crud.accept_friend_request(db_session, friend_request.id, user2.id)
        
        assert accepted.status == "accepted"
        assert crud.are_friends(db_session, user1.id, user2.id) is True
        
        # Check notification was created for sender
        notifications = crud.get_notifications(db_session, user1.id)
        assert len(notifications) == 1
        assert notifications[0].type == "friend_request_accepted"
    
    def test_accept_friend_request_wrong_user(self, db_session, test_user_data):
        """Test accepting friend request as wrong user."""
        # Create three users
        user1_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user1 = crud.create_user(db_session, user1_create, hashed_password)
        
        user_data2 = test_user_data.copy()
        user_data2["email"] = "user2@example.com"
        user_data2["username"] = "user2"
        user2_create = schemas.UserCreate(**user_data2)
        user2 = crud.create_user(db_session, user2_create, hashed_password)
        
        user_data3 = test_user_data.copy()
        user_data3["email"] = "user3@example.com"
        user_data3["username"] = "user3"
        user3_create = schemas.UserCreate(**user_data3)
        user3 = crud.create_user(db_session, user3_create, hashed_password)
        
        # User1 sends request to user2
        friend_request = crud.create_friend_request(db_session, user1.id, user2.id)
        
        # User3 tries to accept (should fail)
        with pytest.raises(ValueError, match="only accept friend requests sent to you"):
            crud.accept_friend_request(db_session, friend_request.id, user3.id)
    
    def test_deny_friend_request(self, db_session, test_user_data):
        """Test denying a friend request."""
        # Create two users
        user1_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user1 = crud.create_user(db_session, user1_create, hashed_password)
        
        user_data2 = test_user_data.copy()
        user_data2["email"] = "user2@example.com"
        user_data2["username"] = "user2"
        user2_create = schemas.UserCreate(**user_data2)
        user2 = crud.create_user(db_session, user2_create, hashed_password)
        
        # Create friend request
        friend_request = crud.create_friend_request(db_session, user1.id, user2.id)
        
        # Deny request
        denied = crud.deny_friend_request(db_session, friend_request.id, user2.id)
        
        assert denied.status == "denied"
        assert crud.are_friends(db_session, user1.id, user2.id) is False
    
    def test_cancel_friend_request(self, db_session, test_user_data):
        """Test cancelling a sent friend request."""
        # Create two users
        user1_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user1 = crud.create_user(db_session, user1_create, hashed_password)
        
        user_data2 = test_user_data.copy()
        user_data2["email"] = "user2@example.com"
        user_data2["username"] = "user2"
        user2_create = schemas.UserCreate(**user_data2)
        user2 = crud.create_user(db_session, user2_create, hashed_password)
        
        # Create friend request
        friend_request = crud.create_friend_request(db_session, user1.id, user2.id)
        
        # Cancel request
        cancelled = crud.cancel_friend_request(db_session, friend_request.id, user1.id)
        
        assert cancelled.status == "cancelled"
    
    def test_expire_friend_requests(self, db_session, test_user_data):
        """Test expiring old friend requests."""
        # Create two users
        user1_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user1 = crud.create_user(db_session, user1_create, hashed_password)
        
        user_data2 = test_user_data.copy()
        user_data2["email"] = "user2@example.com"
        user_data2["username"] = "user2"
        user2_create = schemas.UserCreate(**user_data2)
        user2 = crud.create_user(db_session, user2_create, hashed_password)
        
        # Create friend request and manually set expires_at to past
        friend_request = models.FriendRequest(
            sender_id=user1.id,
            receiver_id=user2.id,
            status="pending",
            expires_at=datetime.utcnow() - timedelta(days=1)
        )
        db_session.add(friend_request)
        db_session.commit()
        
        # Expire requests
        expired_count = crud.expire_friend_requests(db_session)
        
        assert expired_count == 1
        db_session.refresh(friend_request)
        assert friend_request.status == "expired"


class TestFriendshipCRUD:
    """Test friendship CRUD operations."""
    
    def test_create_friendship(self, db_session, test_user_data):
        """Test creating a friendship."""
        # Create two users
        user1_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user1 = crud.create_user(db_session, user1_create, hashed_password)
        
        user_data2 = test_user_data.copy()
        user_data2["email"] = "user2@example.com"
        user_data2["username"] = "user2"
        user2_create = schemas.UserCreate(**user_data2)
        user2 = crud.create_user(db_session, user2_create, hashed_password)
        
        # Create friendship
        user1_id = min(user1.id, user2.id)
        user2_id = max(user1.id, user2.id)
        friendship = crud.create_friendship(db_session, user1_id, user2_id)
        
        assert friendship is not None
        assert friendship.user1_id == user1_id
        assert friendship.user2_id == user2_id
    
    def test_create_friendship_duplicate(self, db_session, test_user_data):
        """Test creating duplicate friendship returns existing."""
        # Create two users
        user1_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user1 = crud.create_user(db_session, user1_create, hashed_password)
        
        user_data2 = test_user_data.copy()
        user_data2["email"] = "user2@example.com"
        user_data2["username"] = "user2"
        user2_create = schemas.UserCreate(**user_data2)
        user2 = crud.create_user(db_session, user2_create, hashed_password)
        
        # Create friendship
        user1_id = min(user1.id, user2.id)
        user2_id = max(user1.id, user2.id)
        friendship1 = crud.create_friendship(db_session, user1_id, user2_id)
        
        # Try to create duplicate
        friendship2 = crud.create_friendship(db_session, user1_id, user2_id)
        
        assert friendship1.id == friendship2.id
    
    def test_get_friends(self, db_session, test_user_data):
        """Test getting friends for a user."""
        # Create three users
        user1_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user1 = crud.create_user(db_session, user1_create, hashed_password)
        
        user_data2 = test_user_data.copy()
        user_data2["email"] = "user2@example.com"
        user_data2["username"] = "user2"
        user2_create = schemas.UserCreate(**user_data2)
        user2 = crud.create_user(db_session, user2_create, hashed_password)
        
        user_data3 = test_user_data.copy()
        user_data3["email"] = "user3@example.com"
        user_data3["username"] = "user3"
        user3_create = schemas.UserCreate(**user_data3)
        user3 = crud.create_user(db_session, user3_create, hashed_password)
        
        # Create friendships
        user1_id = min(user1.id, user2.id)
        user2_id = max(user1.id, user2.id)
        crud.create_friendship(db_session, user1_id, user2_id)
        
        user1_id = min(user1.id, user3.id)
        user3_id = max(user1.id, user3.id)
        crud.create_friendship(db_session, user1_id, user3_id)
        
        # Get friends for user1
        friends = crud.get_friends(db_session, user1.id)
        
        assert len(friends) == 2
        friend_usernames = {f.username for f in friends}
        assert friend_usernames == {"user2", "user3"}
    
    def test_are_friends(self, db_session, test_user_data):
        """Test checking if two users are friends."""
        # Create two users
        user1_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user1 = crud.create_user(db_session, user1_create, hashed_password)
        
        user_data2 = test_user_data.copy()
        user_data2["email"] = "user2@example.com"
        user_data2["username"] = "user2"
        user2_create = schemas.UserCreate(**user_data2)
        user2 = crud.create_user(db_session, user2_create, hashed_password)
        
        # Not friends initially
        assert crud.are_friends(db_session, user1.id, user2.id) is False
        
        # Create friendship
        user1_id = min(user1.id, user2.id)
        user2_id = max(user1.id, user2.id)
        crud.create_friendship(db_session, user1_id, user2_id)
        
        # Now friends
        assert crud.are_friends(db_session, user1.id, user2.id) is True
    
    def test_remove_friendship(self, db_session, test_user_data):
        """Test removing a friendship."""
        # Create two users
        user1_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user1 = crud.create_user(db_session, user1_create, hashed_password)
        
        user_data2 = test_user_data.copy()
        user_data2["email"] = "user2@example.com"
        user_data2["username"] = "user2"
        user2_create = schemas.UserCreate(**user_data2)
        user2 = crud.create_user(db_session, user2_create, hashed_password)
        
        # Create friendship
        user1_id = min(user1.id, user2.id)
        user2_id = max(user1.id, user2.id)
        crud.create_friendship(db_session, user1_id, user2_id)
        
        # Remove friendship
        success = crud.remove_friendship(db_session, user1.id, user2.id)
        
        assert success is True
        assert crud.are_friends(db_session, user1.id, user2.id) is False
    
    def test_remove_friendship_nonexistent(self, db_session, test_user_data):
        """Test removing nonexistent friendship."""
        # Create two users
        user1_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user1 = crud.create_user(db_session, user1_create, hashed_password)
        
        user_data2 = test_user_data.copy()
        user_data2["email"] = "user2@example.com"
        user_data2["username"] = "user2"
        user2_create = schemas.UserCreate(**user_data2)
        user2 = crud.create_user(db_session, user2_create, hashed_password)
        
        # Try to remove nonexistent friendship
        success = crud.remove_friendship(db_session, user1.id, user2.id)
        
        assert success is False


class TestNotificationCRUD:
    """Test notification CRUD operations."""
    
    def test_create_notification(self, db_session, test_user_data):
        """Test creating a notification."""
        # Create user
        user_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user = crud.create_user(db_session, user_create, hashed_password)
        
        # Create notification
        notification = crud.create_notification(
            db_session,
            user.id,
            "test_type",
            "Test message"
        )
        
        assert notification is not None
        assert notification.user_id == user.id
        assert notification.type == "test_type"
        assert notification.message == "Test message"
        assert notification.read_at is None
    
    def test_get_notifications(self, db_session, test_user_data):
        """Test getting notifications for a user."""
        # Create user
        user_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user = crud.create_user(db_session, user_create, hashed_password)
        
        # Create multiple notifications with small delays to ensure distinct timestamps
        import time
        crud.create_notification(db_session, user.id, "type1", "Message 1")
        time.sleep(0.01)  # Small delay to ensure distinct timestamps
        crud.create_notification(db_session, user.id, "type2", "Message 2")
        time.sleep(0.01)  # Small delay to ensure distinct timestamps
        crud.create_notification(db_session, user.id, "type3", "Message 3")
        
        # Get notifications
        notifications = crud.get_notifications(db_session, user.id)
        
        assert len(notifications) == 3
        # Should be ordered newest first
        assert notifications[0].message == "Message 3", f"Expected 'Message 3' first, got '{notifications[0].message}'. Order: {[n.message for n in notifications]}"
        assert notifications[1].message == "Message 2", f"Expected 'Message 2' second, got '{notifications[1].message}'. Order: {[n.message for n in notifications]}"
        assert notifications[2].message == "Message 1", f"Expected 'Message 1' third, got '{notifications[2].message}'. Order: {[n.message for n in notifications]}"
    
    def test_get_unread_notification_count(self, db_session, test_user_data):
        """Test getting unread notification count."""
        # Create user
        user_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user = crud.create_user(db_session, user_create, hashed_password)
        
        # Create notifications
        notif1 = crud.create_notification(db_session, user.id, "type1", "Message 1")
        notif2 = crud.create_notification(db_session, user.id, "type2", "Message 2")
        crud.create_notification(db_session, user.id, "type3", "Message 3")
        
        # Mark one as read
        crud.mark_notification_read(db_session, notif1.id, user.id)
        
        # Get unread count
        count = crud.get_unread_notification_count(db_session, user.id)
        
        assert count == 2
    
    def test_mark_notification_read(self, db_session, test_user_data):
        """Test marking a notification as read."""
        # Create user
        user_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user = crud.create_user(db_session, user_create, hashed_password)
        
        # Create notification
        notification = crud.create_notification(db_session, user.id, "type1", "Message 1")
        
        # Mark as read
        marked = crud.mark_notification_read(db_session, notification.id, user.id)
        
        assert marked is not None
        assert marked.read_at is not None
    
    def test_delete_notification(self, db_session, test_user_data):
        """Test deleting a notification."""
        # Create user
        user_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user = crud.create_user(db_session, user_create, hashed_password)
        
        # Create notification
        notification = crud.create_notification(db_session, user.id, "type1", "Message 1")
        
        # Delete notification
        success = crud.delete_notification(db_session, notification.id, user.id)
        
        assert success is True
        notifications = crud.get_notifications(db_session, user.id)
        assert len(notifications) == 0
    
    def test_delete_notification_wrong_user(self, db_session, test_user_data):
        """Test deleting notification as wrong user."""
        # Create two users
        user1_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user1 = crud.create_user(db_session, user1_create, hashed_password)
        
        user_data2 = test_user_data.copy()
        user_data2["email"] = "user2@example.com"
        user_data2["username"] = "user2"
        user2_create = schemas.UserCreate(**user_data2)
        user2 = crud.create_user(db_session, user2_create, hashed_password)
        
        # Create notification for user1
        notification = crud.create_notification(db_session, user1.id, "type1", "Message 1")
        
        # User2 tries to delete (should fail)
        success = crud.delete_notification(db_session, notification.id, user2.id)
        
        assert success is False
        notifications = crud.get_notifications(db_session, user1.id)
        assert len(notifications) == 1


class TestFriendsEndpoints:
    """Test friends API endpoints."""
    
    def test_send_friend_request_success(self, client, test_user_data, db_session):
        """Test sending friend request successfully."""
        # Register and verify two users
        register_response1 = client.post("/auth/register", json=test_user_data)
        user1_id = register_response1.json()["id"]
        user1 = crud.get_user_by_id(db_session, user1_id)
        user1.is_verified = True
        db_session.commit()
        
        user_data2 = test_user_data.copy()
        user_data2["email"] = "user2@example.com"
        user_data2["username"] = "user2"
        register_response2 = client.post("/auth/register", json=user_data2)
        user2_id = register_response2.json()["id"]
        user2 = crud.get_user_by_id(db_session, user2_id)
        user2.is_verified = True
        db_session.commit()
        
        # Login as user1
        login_response = client.post(
            "/auth/login",
            data={"username": test_user_data["username"], "password": test_user_data["password"]}
        )
        token = login_response.json()["access_token"]
        client.headers = {"Authorization": f"Bearer {token}"}
        
        # Send friend request
        response = client.post(
            "/friends/request",
            json={"receiver_username": "user2"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["sender_id"] == user1_id
        assert data["receiver_id"] == user2_id
        assert data["status"] == "pending"
    
    def test_send_friend_request_user_not_found(self, client, test_user_data, db_session):
        """Test sending friend request to nonexistent user."""
        # Register and verify user
        register_response = client.post("/auth/register", json=test_user_data)
        user_id = register_response.json()["id"]
        user = crud.get_user_by_id(db_session, user_id)
        user.is_verified = True
        db_session.commit()
        
        # Login
        login_response = client.post(
            "/auth/login",
            data={"username": test_user_data["username"], "password": test_user_data["password"]}
        )
        token = login_response.json()["access_token"]
        client.headers = {"Authorization": f"Bearer {token}"}
        
        # Send friend request to nonexistent user
        response = client.post(
            "/friends/request",
            json={"receiver_username": "nonexistent"}
        )
        
        assert response.status_code == 404
    
    def test_send_friend_request_to_self(self, client, test_user_data, db_session):
        """Test sending friend request to yourself."""
        # Register and verify user
        register_response = client.post("/auth/register", json=test_user_data)
        user_id = register_response.json()["id"]
        user = crud.get_user_by_id(db_session, user_id)
        user.is_verified = True
        db_session.commit()
        
        # Login
        login_response = client.post(
            "/auth/login",
            data={"username": test_user_data["username"], "password": test_user_data["password"]}
        )
        token = login_response.json()["access_token"]
        client.headers = {"Authorization": f"Bearer {token}"}
        
        # Send friend request to self
        response = client.post(
            "/friends/request",
            json={"receiver_username": test_user_data["username"]}
        )
        
        assert response.status_code == 400
    
    def test_get_friend_requests(self, client, test_user_data, db_session):
        """Test getting friend requests."""
        # Register and verify three users
        register_response1 = client.post("/auth/register", json=test_user_data)
        user1_id = register_response1.json()["id"]
        user1 = crud.get_user_by_id(db_session, user1_id)
        user1.is_verified = True
        db_session.commit()
        
        user_data2 = test_user_data.copy()
        user_data2["email"] = "user2@example.com"
        user_data2["username"] = "user2"
        register_response2 = client.post("/auth/register", json=user_data2)
        user2_id = register_response2.json()["id"]
        user2 = crud.get_user_by_id(db_session, user2_id)
        user2.is_verified = True
        db_session.commit()
        
        user_data3 = test_user_data.copy()
        user_data3["email"] = "user3@example.com"
        user_data3["username"] = "user3"
        register_response3 = client.post("/auth/register", json=user_data3)
        user3_id = register_response3.json()["id"]
        user3 = crud.get_user_by_id(db_session, user3_id)
        user3.is_verified = True
        db_session.commit()
        
        # Login as user1 and send request to user2
        login_response1 = client.post(
            "/auth/login",
            data={"username": test_user_data["username"], "password": test_user_data["password"]}
        )
        token1 = login_response1.json()["access_token"]
        client.headers = {"Authorization": f"Bearer {token1}"}
        request1_response = client.post("/friends/request", json={"receiver_username": "user2"})
        assert request1_response.status_code == 200
        
        # Login as user2 and send request to user3 (not user1, since user1 already sent to user2)
        login_response2 = client.post(
            "/auth/login",
            data={"username": "user2", "password": test_user_data["password"]}
        )
        token2 = login_response2.json()["access_token"]
        client.headers = {"Authorization": f"Bearer {token2}"}
        request2_response = client.post("/friends/request", json={"receiver_username": "user3"})
        assert request2_response.status_code == 200
        
        # Get requests as user2
        response = client.get("/friends/requests")
        
        assert response.status_code == 200
        data = response.json()
        # User2 should have:
        # - sent: 1 request (user2 -> user3)
        # - received: 1 request (user1 -> user2)
        assert len(data["sent"]) == 1
        assert len(data["received"]) == 1
        assert data["sent"][0]["receiver_id"] == user3_id
        assert data["received"][0]["sender_id"] == user1_id
    
    def test_accept_friend_request(self, client, test_user_data, db_session):
        """Test accepting a friend request."""
        # Register and verify two users
        register_response1 = client.post("/auth/register", json=test_user_data)
        user1_id = register_response1.json()["id"]
        user1 = crud.get_user_by_id(db_session, user1_id)
        user1.is_verified = True
        db_session.commit()
        
        user_data2 = test_user_data.copy()
        user_data2["email"] = "user2@example.com"
        user_data2["username"] = "user2"
        register_response2 = client.post("/auth/register", json=user_data2)
        user2_id = register_response2.json()["id"]
        user2 = crud.get_user_by_id(db_session, user2_id)
        user2.is_verified = True
        db_session.commit()
        
        # Login as user1 and send request
        login_response1 = client.post(
            "/auth/login",
            data={"username": test_user_data["username"], "password": test_user_data["password"]}
        )
        token1 = login_response1.json()["access_token"]
        client.headers = {"Authorization": f"Bearer {token1}"}
        request_response = client.post("/friends/request", json={"receiver_username": "user2"})
        request_id = request_response.json()["id"]
        
        # Login as user2 and accept
        login_response2 = client.post(
            "/auth/login",
            data={"username": "user2", "password": test_user_data["password"]}
        )
        token2 = login_response2.json()["access_token"]
        client.headers = {"Authorization": f"Bearer {token2}"}
        response = client.post(f"/friends/requests/{request_id}/accept")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        
        # Check friendship was created
        assert crud.are_friends(db_session, user1_id, user2_id) is True
    
    def test_deny_friend_request(self, client, test_user_data, db_session):
        """Test denying a friend request."""
        # Register and verify two users
        register_response1 = client.post("/auth/register", json=test_user_data)
        user1_id = register_response1.json()["id"]
        user1 = crud.get_user_by_id(db_session, user1_id)
        user1.is_verified = True
        db_session.commit()
        
        user_data2 = test_user_data.copy()
        user_data2["email"] = "user2@example.com"
        user_data2["username"] = "user2"
        register_response2 = client.post("/auth/register", json=user_data2)
        user2_id = register_response2.json()["id"]
        user2 = crud.get_user_by_id(db_session, user2_id)
        user2.is_verified = True
        db_session.commit()
        
        # Login as user1 and send request
        login_response1 = client.post(
            "/auth/login",
            data={"username": test_user_data["username"], "password": test_user_data["password"]}
        )
        token1 = login_response1.json()["access_token"]
        client.headers = {"Authorization": f"Bearer {token1}"}
        request_response = client.post("/friends/request", json={"receiver_username": "user2"})
        request_id = request_response.json()["id"]
        
        # Login as user2 and deny
        login_response2 = client.post(
            "/auth/login",
            data={"username": "user2", "password": test_user_data["password"]}
        )
        token2 = login_response2.json()["access_token"]
        client.headers = {"Authorization": f"Bearer {token2}"}
        response = client.post(f"/friends/requests/{request_id}/deny")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "denied"
    
    def test_cancel_friend_request(self, client, test_user_data, db_session):
        """Test cancelling a sent friend request."""
        # Register and verify two users
        register_response1 = client.post("/auth/register", json=test_user_data)
        user1_id = register_response1.json()["id"]
        user1 = crud.get_user_by_id(db_session, user1_id)
        user1.is_verified = True
        db_session.commit()
        
        user_data2 = test_user_data.copy()
        user_data2["email"] = "user2@example.com"
        user_data2["username"] = "user2"
        register_response2 = client.post("/auth/register", json=user_data2)
        user2_id = register_response2.json()["id"]
        user2 = crud.get_user_by_id(db_session, user2_id)
        user2.is_verified = True
        db_session.commit()
        
        # Login as user1 and send request
        login_response = client.post(
            "/auth/login",
            data={"username": test_user_data["username"], "password": test_user_data["password"]}
        )
        token = login_response.json()["access_token"]
        client.headers = {"Authorization": f"Bearer {token}"}
        request_response = client.post("/friends/request", json={"receiver_username": "user2"})
        request_id = request_response.json()["id"]
        
        # Cancel request
        response = client.delete(f"/friends/requests/{request_id}")
        
        assert response.status_code == 200
    
    def test_get_friends(self, client, test_user_data, db_session):
        """Test getting friends list."""
        # Register and verify two users
        register_response1 = client.post("/auth/register", json=test_user_data)
        user1_id = register_response1.json()["id"]
        user1 = crud.get_user_by_id(db_session, user1_id)
        user1.is_verified = True
        db_session.commit()
        
        user_data2 = test_user_data.copy()
        user_data2["email"] = "user2@example.com"
        user_data2["username"] = "user2"
        register_response2 = client.post("/auth/register", json=user_data2)
        user2_id = register_response2.json()["id"]
        user2 = crud.get_user_by_id(db_session, user2_id)
        user2.is_verified = True
        db_session.commit()
        
        # Create friendship directly
        user1_id_small = min(user1_id, user2_id)
        user2_id_large = max(user1_id, user2_id)
        crud.create_friendship(db_session, user1_id_small, user2_id_large)
        
        # Login as user1
        login_response = client.post(
            "/auth/login",
            data={"username": test_user_data["username"], "password": test_user_data["password"]}
        )
        token = login_response.json()["access_token"]
        client.headers = {"Authorization": f"Bearer {token}"}
        
        # Get friends
        response = client.get("/friends")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["friend"]["username"] == "user2"
    
    def test_unfriend_user(self, client, test_user_data, db_session):
        """Test unfriending a user."""
        # Register and verify two users
        register_response1 = client.post("/auth/register", json=test_user_data)
        user1_id = register_response1.json()["id"]
        user1 = crud.get_user_by_id(db_session, user1_id)
        user1.is_verified = True
        db_session.commit()
        
        user_data2 = test_user_data.copy()
        user_data2["email"] = "user2@example.com"
        user_data2["username"] = "user2"
        register_response2 = client.post("/auth/register", json=user_data2)
        user2_id = register_response2.json()["id"]
        user2 = crud.get_user_by_id(db_session, user2_id)
        user2.is_verified = True
        db_session.commit()
        
        # Create friendship
        user1_id_small = min(user1_id, user2_id)
        user2_id_large = max(user1_id, user2_id)
        crud.create_friendship(db_session, user1_id_small, user2_id_large)
        
        # Login as user1
        login_response = client.post(
            "/auth/login",
            data={"username": test_user_data["username"], "password": test_user_data["password"]}
        )
        token = login_response.json()["access_token"]
        client.headers = {"Authorization": f"Bearer {token}"}
        
        # Unfriend user2
        response = client.delete(f"/friends/{user2_id}")
        
        assert response.status_code == 200
        assert crud.are_friends(db_session, user1_id, user2_id) is False


class TestNotificationEndpoints:
    """Test notification API endpoints."""
    
    def test_get_notifications(self, client, test_user_data, db_session):
        """Test getting notifications."""
        # Register and verify user
        register_response = client.post("/auth/register", json=test_user_data)
        user_id = register_response.json()["id"]
        user = crud.get_user_by_id(db_session, user_id)
        user.is_verified = True
        db_session.commit()
        
        # Create notifications with a small delay to ensure different timestamps
        import time
        crud.create_notification(db_session, user_id, "type1", "Message 1")
        time.sleep(0.01)  # Small delay to ensure different timestamps
        crud.create_notification(db_session, user_id, "type2", "Message 2")
        
        # Login
        login_response = client.post(
            "/auth/login",
            data={"username": test_user_data["username"], "password": test_user_data["password"]}
        )
        token = login_response.json()["access_token"]
        client.headers = {"Authorization": f"Bearer {token}"}
        
        # Get notifications
        response = client.get("/notifications")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2, f"Expected 2 notifications, got {len(data)}: {data}"
        # Check that notifications are ordered newest first
        messages = [notif["message"] for notif in data]
        assert "Message 2" in messages, f"Expected 'Message 2' in {messages}"
        assert "Message 1" in messages, f"Expected 'Message 1' in {messages}"
        # The first one should be Message 2 (newest, created last)
        assert data[0]["message"] == "Message 2", f"Expected 'Message 2' first, but got order: {messages}"
        assert data[1]["message"] == "Message 1", f"Expected 'Message 1' second, but got order: {messages}"
    
    def test_get_notification_count(self, client, test_user_data, db_session):
        """Test getting notification count."""
        # Register and verify user
        register_response = client.post("/auth/register", json=test_user_data)
        user_id = register_response.json()["id"]
        user = crud.get_user_by_id(db_session, user_id)
        user.is_verified = True
        db_session.commit()
        
        # Create notifications
        notif1 = crud.create_notification(db_session, user_id, "type1", "Message 1")
        crud.create_notification(db_session, user_id, "type2", "Message 2")
        crud.create_notification(db_session, user_id, "type3", "Message 3")
        
        # Mark one as read
        crud.mark_notification_read(db_session, notif1.id, user_id)
        
        # Login
        login_response = client.post(
            "/auth/login",
            data={"username": test_user_data["username"], "password": test_user_data["password"]}
        )
        token = login_response.json()["access_token"]
        client.headers = {"Authorization": f"Bearer {token}"}
        
        # Get count
        response = client.get("/notifications/count")
        
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
    
    def test_dismiss_notification(self, client, test_user_data, db_session):
        """Test dismissing a notification."""
        # Register and verify user
        register_response = client.post("/auth/register", json=test_user_data)
        user_id = register_response.json()["id"]
        user = crud.get_user_by_id(db_session, user_id)
        user.is_verified = True
        db_session.commit()
        
        # Create notification
        notification = crud.create_notification(db_session, user_id, "type1", "Message 1")
        
        # Login
        login_response = client.post(
            "/auth/login",
            data={"username": test_user_data["username"], "password": test_user_data["password"]}
        )
        token = login_response.json()["access_token"]
        client.headers = {"Authorization": f"Bearer {token}"}
        
        # Dismiss notification
        response = client.delete(f"/notifications/{notification.id}")
        
        assert response.status_code == 200
        notifications = crud.get_notifications(db_session, user_id)
        assert len(notifications) == 0
    
    def test_dismiss_notification_not_found(self, client, test_user_data, db_session):
        """Test dismissing nonexistent notification."""
        # Register and verify user
        register_response = client.post("/auth/register", json=test_user_data)
        user_id = register_response.json()["id"]
        user = crud.get_user_by_id(db_session, user_id)
        user.is_verified = True
        db_session.commit()
        
        # Login
        login_response = client.post(
            "/auth/login",
            data={"username": test_user_data["username"], "password": test_user_data["password"]}
        )
        token = login_response.json()["access_token"]
        client.headers = {"Authorization": f"Bearer {token}"}
        
        # Dismiss nonexistent notification
        response = client.delete("/notifications/99999")
        
        assert response.status_code == 404

