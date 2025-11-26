"""
Tests for authentication endpoints and utilities.
"""
import pytest
from app import auth, crud, models
from app.database import SessionLocal


class TestPasswordHashing:
    """Test password hashing and verification."""
    
    def test_hash_password(self):
        """Test that passwords are hashed correctly."""
        password = "testpassword123"
        hashed = auth.get_password_hash(password)
        
        assert hashed != password
        assert len(hashed) > 0
        assert hashed.startswith("$2b$")  # bcrypt hash format
    
    def test_verify_password_correct(self):
        """Test password verification with correct password."""
        password = "testpassword123"
        hashed = auth.get_password_hash(password)
        
        assert auth.verify_password(password, hashed) is True
    
    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password."""
        password = "testpassword123"
        hashed = auth.get_password_hash(password)
        
        assert auth.verify_password("wrongpassword", hashed) is False


class TestJWTTokens:
    """Test JWT token creation and validation."""
    
    def test_create_access_token(self):
        """Test that access tokens are created successfully."""
        data = {"sub": "testuser"}
        token = auth.create_access_token(data)
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_decode_valid_token(self):
        """Test decoding a valid token."""
        data = {"sub": "testuser"}
        token = auth.create_access_token(data)
        decoded = auth.decode_access_token(token)
        
        assert decoded is not None
        assert decoded["sub"] == "testuser"
        assert "exp" in decoded
    
    def test_decode_invalid_token(self):
        """Test decoding an invalid token."""
        invalid_token = "invalid.token.here"
        decoded = auth.decode_access_token(invalid_token)
        
        assert decoded is None


class TestAuthEndpoints:
    """Test authentication API endpoints."""
    
    def test_register_new_user(self, client, test_user_data):
        """Test registering a new user."""
        response = client.post("/auth/register", json=test_user_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == test_user_data["email"]
        assert data["username"] == test_user_data["username"]
        assert "id" in data
        assert data["is_verified"] is False
        assert "hashed_password" not in data  # Password should not be returned
    
    def test_register_duplicate_email(self, client, test_user_data):
        """Test registering with duplicate email."""
        # Register first user
        client.post("/auth/register", json=test_user_data)
        
        # Try to register with same email
        duplicate_data = test_user_data.copy()
        duplicate_data["username"] = "differentuser"
        response = client.post("/auth/register", json=duplicate_data)
        
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()
    
    def test_register_duplicate_username(self, client, test_user_data):
        """Test registering with duplicate username."""
        # Register first user
        client.post("/auth/register", json=test_user_data)
        
        # Try to register with same username
        duplicate_data = test_user_data.copy()
        duplicate_data["email"] = "different@example.com"
        response = client.post("/auth/register", json=duplicate_data)
        
        assert response.status_code == 400
        assert "username" in response.json()["detail"].lower()
    
    def test_login_success(self, client, test_user_data):
        """Test successful login."""
        # Register user first
        client.post("/auth/register", json=test_user_data)
        
        # Login
        response = client.post(
            "/auth/login",
            data={
                "username": test_user_data["username"],
                "password": test_user_data["password"]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
    
    def test_login_with_email(self, client, test_user_data):
        """Test login using email instead of username."""
        # Register user first
        client.post("/auth/register", json=test_user_data)
        
        # Login with email
        response = client.post(
            "/auth/login",
            data={
                "username": test_user_data["email"],
                "password": test_user_data["password"]
            }
        )
        
        assert response.status_code == 200
        assert "access_token" in response.json()
    
    def test_login_wrong_password(self, client, test_user_data):
        """Test login with wrong password."""
        # Register user first
        client.post("/auth/register", json=test_user_data)
        
        # Try to login with wrong password
        response = client.post(
            "/auth/login",
            data={
                "username": test_user_data["username"],
                "password": "wrongpassword"
            }
        )
        
        assert response.status_code == 401
    
    def test_login_nonexistent_user(self, client):
        """Test login with non-existent user."""
        response = client.post(
            "/auth/login",
            data={
                "username": "nonexistent",
                "password": "password123"
            }
        )
        
        assert response.status_code == 401


class TestEmailVerification:
    """Test email verification functionality."""
    
    def test_verify_email_success(self, client, test_user_data, db_session):
        """Test successful email verification."""
        # Register user
        register_response = client.post("/auth/register", json=test_user_data)
        user_id = register_response.json()["id"]
        
        # Get verification token from database
        user = crud.get_user_by_id(db_session, user_id)
        assert user is not None
        assert user.verification_token is not None
        
        # Verify email
        response = client.get(f"/auth/verify-email?token={user.verification_token}")
        
        assert response.status_code == 200
        assert "verified" in response.json()["message"].lower()
        
        # Check user is now verified
        db_session.refresh(user)
        assert user.is_verified is True
        assert user.verification_token is None
    
    def test_verify_email_invalid_token(self, client):
        """Test email verification with invalid token."""
        response = client.get("/auth/verify-email?token=invalid_token_12345")
        
        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower() or "expired" in response.json()["detail"].lower()


class TestPasswordReset:
    """Test password reset functionality."""
    
    def test_request_password_reset(self, client, test_user_data):
        """Test requesting password reset."""
        # Register user first
        client.post("/auth/register", json=test_user_data)
        
        # Request password reset
        response = client.post(f"/auth/request-password-reset?email={test_user_data['email']}")
        
        assert response.status_code == 200
        assert "email" in response.json()["message"].lower()
    
    def test_request_password_reset_nonexistent_email(self, client):
        """Test password reset request for non-existent email (should not reveal if email exists)."""
        response = client.post("/auth/request-password-reset?email=nonexistent@example.com")
        
        # Should return same message for security (don't reveal if email exists)
        assert response.status_code == 200
    
    def test_reset_password_success(self, client, test_user_data, db_session):
        """Test successful password reset."""
        # Register user
        register_response = client.post("/auth/register", json=test_user_data)
        user_id = register_response.json()["id"]
        
        # Request password reset
        client.post(f"/auth/request-password-reset?email={test_user_data['email']}")
        
        # Get reset token from database
        user = crud.get_user_by_id(db_session, user_id)
        assert user.reset_token is not None
        
        # Reset password
        new_password = "newpassword123"
        response = client.post(
            f"/auth/reset-password?token={user.reset_token}&new_password={new_password}"
        )
        
        assert response.status_code == 200
        assert "successfully" in response.json()["message"].lower()
        
        # Verify can login with new password
        login_response = client.post(
            "/auth/login",
            data={
                "username": test_user_data["username"],
                "password": new_password
            }
        )
        assert login_response.status_code == 200
    
    def test_reset_password_invalid_token(self, client):
        """Test password reset with invalid token."""
        response = client.post("/auth/reset-password?token=invalid_token&new_password=newpass123")
        
        assert response.status_code == 400

