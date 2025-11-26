"""
Email utilities for OmniTrackr.
Handles sending verification and password reset emails.
"""
import os
from typing import List
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from itsdangerous import URLSafeTimedSerializer
from dotenv import load_dotenv

load_dotenv()

# Email configuration
conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME", ""),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD", ""),
    MAIL_FROM=os.getenv("MAIL_FROM", "noreply@omnitrackr.com"),
    MAIL_PORT=int(os.getenv("MAIL_PORT", "587")),
    MAIL_SERVER=os.getenv("MAIL_SERVER", "smtp.gmail.com"),
    MAIL_STARTTLS=os.getenv("MAIL_STARTTLS", "True").lower() == "true",
    MAIL_SSL_TLS=os.getenv("MAIL_SSL_TLS", "False").lower() == "true",
    USE_CREDENTIALS=os.getenv("USE_CREDENTIALS", "True").lower() == "true",
    VALIDATE_CERTS=os.getenv("VALIDATE_CERTS", "True").lower() == "true"
)

# Token serializer for generating secure tokens
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
serializer = URLSafeTimedSerializer(SECRET_KEY)

# Base URL for the application
APP_URL = os.getenv("APP_URL", "http://localhost:8000")


def generate_verification_token(email: str) -> str:
    """Generate a secure verification token for email verification."""
    return serializer.dumps(email, salt="email-verification")


def verify_token(token: str, max_age: int = 3600) -> str:
    """
    Verify a token and return the email if valid.
    
    Args:
        token: The token to verify
        max_age: Maximum age of the token in seconds (default 1 hour)
    
    Returns:
        The email address if token is valid
    
    Raises:
        Exception if token is invalid or expired
    """
    try:
        email = serializer.loads(token, salt="email-verification", max_age=max_age)
        return email
    except Exception:
        raise


def generate_reset_token(email: str) -> str:
    """Generate a secure token for password reset."""
    return serializer.dumps(email, salt="password-reset")


def verify_reset_token(token: str, max_age: int = 3600) -> str:
    """
    Verify a password reset token and return the email if valid.
    
    Args:
        token: The reset token to verify
        max_age: Maximum age of the token in seconds (default 1 hour)
    
    Returns:
        The email address if token is valid
    
    Raises:
        Exception if token is invalid or expired
    """
    try:
        email = serializer.loads(token, salt="password-reset", max_age=max_age)
        return email
    except Exception:
        raise


async def send_verification_email(email: str, username: str, token: str):
    """
    Send email verification email to user.
    
    Args:
        email: User's email address
        username: User's username
        token: Verification token
    """
    verification_url = f"{APP_URL}/?token={token}&email_verified=true"
    
    html = f"""
    <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
                <h1 style="color: white; margin: 0;">Welcome to OmniTrackr!</h1>
            </div>
            <div style="padding: 30px; background-color: #f9f9f9;">
                <h2>Hi {username},</h2>
                <p>Thank you for registering with OmniTrackr! To complete your registration, please verify your email address by clicking the button below:</p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{verification_url}" 
                       style="background-color: #667eea; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                        Verify Email Address
                    </a>
                </div>
                <p>Or copy and paste this link into your browser:</p>
                <p style="word-break: break-all; color: #667eea;">{verification_url}</p>
                <p><strong>This link will expire in 1 hour.</strong></p>
                <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                <p style="color: #666; font-size: 12px;">
                    If you didn't create an account with OmniTrackr, you can safely ignore this email.
                </p>
            </div>
        </body>
    </html>
    """
    
    message = MessageSchema(
        subject="Verify Your OmniTrackr Email",
        recipients=[email],
        body=html,
        subtype=MessageType.html
    )
    
    # Only send if email credentials are configured
    if conf.MAIL_USERNAME and conf.MAIL_PASSWORD:
        try:
            import asyncio
            fm = FastMail(conf)
            # Add timeout to prevent hanging (30 seconds)
            await asyncio.wait_for(fm.send_message(message), timeout=30.0)
        except asyncio.TimeoutError:
            print(f"ERROR: Email sending timed out after 30 seconds")
            print(f"Failed to send verification email to {email}")
            print(f"Verification URL (fallback): {verification_url}")
            raise Exception("Email sending timed out. Check your email service configuration.")
        except Exception as e:
            error_msg = str(e)
            print(f"ERROR: Failed to send verification email to {email}")
            print(f"Error: {error_msg}")
            print(f"Verification URL (fallback): {verification_url}")
            # Re-raise the exception so caller knows it failed
            raise Exception(f"Failed to send email: {error_msg}. Check your email service configuration (SMTP server, credentials, network).")
    else:
        # Development mode - just print the verification URL
        print(f"\n{'='*60}")
        print(f"Email Verification Required")
        print(f"{'='*60}")
        print(f"To: {email}")
        print(f"Username: {username}")
        print(f"Verification URL: {verification_url}")
        print(f"{'='*60}\n")


async def send_password_reset_email(email: str, username: str, token: str):
    """
    Send password reset email to user.
    
    Args:
        email: User's email address
        username: User's username
        token: Password reset token
    """
    reset_url = f"{APP_URL}/?reset_token={token}"
    
    html = f"""
    <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
                <h1 style="color: white; margin: 0;">Password Reset Request</h1>
            </div>
            <div style="padding: 30px; background-color: #f9f9f9;">
                <h2>Hi {username},</h2>
                <p>We received a request to reset your OmniTrackr password. Click the button below to create a new password:</p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_url}" 
                       style="background-color: #667eea; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                        Reset Password
                    </a>
                </div>
                <p>Or copy and paste this link into your browser:</p>
                <p style="word-break: break-all; color: #667eea;">{reset_url}</p>
                <p><strong>This link will expire in 1 hour.</strong></p>
                <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                <p style="color: #666; font-size: 12px;">
                    If you didn't request a password reset, you can safely ignore this email. Your password will not be changed.
                </p>
            </div>
        </body>
    </html>
    """
    
    message = MessageSchema(
        subject="Reset Your OmniTrackr Password",
        recipients=[email],
        body=html,
        subtype=MessageType.html
    )
    
    # Only send if email credentials are configured
    if conf.MAIL_USERNAME and conf.MAIL_PASSWORD:
        try:
            import asyncio
            fm = FastMail(conf)
            # Add timeout to prevent hanging (30 seconds)
            await asyncio.wait_for(fm.send_message(message), timeout=30.0)
        except asyncio.TimeoutError:
            print(f"ERROR: Email sending timed out after 30 seconds")
            print(f"Failed to send password reset email to {email}")
            print(f"Reset URL (fallback): {reset_url}")
            raise Exception("Email sending timed out. Check your email service configuration.")
        except Exception as e:
            error_msg = str(e)
            print(f"ERROR: Failed to send password reset email to {email}")
            print(f"Error: {error_msg}")
            print(f"Reset URL (fallback): {reset_url}")
            # Re-raise the exception so caller knows it failed
            raise Exception(f"Failed to send email: {error_msg}. Check your email service configuration (SMTP server, credentials, network).")
    else:
        # Development mode - just print the reset URL
        print(f"\n{'='*60}")
        print(f"Password Reset Requested")
        print(f"{'='*60}")
        print(f"To: {email}")
        print(f"Username: {username}")
        print(f"Reset URL: {reset_url}")
        print(f"{'='*60}\n")

