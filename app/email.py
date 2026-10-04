"""
Email utilities for OmniTrackr.
Handles sending verification and password reset emails.
"""
import os
from html import escape as _escape_html
from html.parser import HTMLParser
from typing import List
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from fastapi_mail.schemas import MultipartSubtypeEnum
from itsdangerous import URLSafeTimedSerializer
from dotenv import load_dotenv

load_dotenv()

# Email configuration
conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME", ""),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD", ""),
    MAIL_FROM=os.getenv("MAIL_FROM", "noreply@omnitrackr.xyz"),
    MAIL_FROM_NAME=os.getenv("MAIL_FROM_NAME", "OmniTrackr"),
    MAIL_PORT=int(os.getenv("MAIL_PORT", "587")),
    MAIL_SERVER=os.getenv("MAIL_SERVER", "smtp.gmail.com"),
    MAIL_STARTTLS=os.getenv("MAIL_STARTTLS", "True").lower() == "true",
    MAIL_SSL_TLS=os.getenv("MAIL_SSL_TLS", "False").lower() == "true",
    USE_CREDENTIALS=os.getenv("USE_CREDENTIALS", "True").lower() == "true",
    VALIDATE_CERTS=os.getenv("VALIDATE_CERTS", "True").lower() == "true"
)

# Token serializer for generating secure tokens
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if ENVIRONMENT == "production":
        raise ValueError("SECRET_KEY must be set in production environment")
    SECRET_KEY = "dev-secret-key-change-in-production"
    import warnings
    warnings.warn("Using default SECRET_KEY - not for production!")
serializer = URLSafeTimedSerializer(SECRET_KEY)

# Base URL for the application
APP_URL = os.getenv("APP_URL", "http://localhost:8000")
# New-account verification links stay valid for 48 hours (people often open them the next day).
VERIFICATION_MAX_AGE = 48 * 3600


class _TextExtractor(HTMLParser):
    """Collects readable text from one of our HTML emails in a single pass (no regexes)."""

    BLOCK_TAGS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "li", "table"}
    SKIP_TAGS = {"script", "style", "head"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0
        self.link_href: str | None = None
        self.link_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
        elif tag == "br":
            self.parts.append("\n")
        elif tag == "a" and not self.skip_depth:
            self.link_href = dict(attrs).get("href")
            self.link_text = []

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS:
            self.skip_depth = max(0, self.skip_depth - 1)
        elif tag == "a" and self.link_href is not None:
            label = " ".join("".join(self.link_text).split())
            self.parts.append(f"{label} ({self.link_href})" if label else self.link_href)
            self.link_href, self.link_text = None, []
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.skip_depth:
            return
        (self.link_text if self.link_href is not None else self.parts).append(data)


def html_to_text(html: str) -> str:
    """A readable plain-text version of one of our HTML emails (links kept as "text (url)")."""
    extractor = _TextExtractor()
    extractor.feed(html)
    extractor.close()
    lines = [" ".join(line.split()) for line in "".join(extractor.parts).splitlines()]
    out, blank = [], False
    for line in lines:
        if line:
            out.append(line)
            blank = False
        elif not blank and out:
            out.append("")
            blank = True
    return "\n".join(out).strip() + "\n"


def html_message(subject: str, recipients: list, html: str, headers: dict | None = None):
    """multipart/alternative: plain text first, HTML last (the part mail apps prefer).

    A text part alongside the HTML is one of the basic things spam filters look for.
    """
    return MessageSchema(
        subject=subject, recipients=recipients,
        body=html_to_text(html), alternative_body=html,
        subtype=MessageType.plain, multipart_subtype=MultipartSubtypeEnum.alternative,
        headers=headers,
    )


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


def generate_email_change_token(old_email: str, new_email: str) -> str:
    """Generate a secure token for email change verification."""
    # Store both emails in the token
    data = f"{old_email}:{new_email}"
    return serializer.dumps(data, salt="email-change")


def verify_email_change_token(token: str, max_age: int = 3600) -> tuple:
    """
    Verify an email change token and return (old_email, new_email) if valid.
    
    Args:
        token: The email change token to verify
        max_age: Maximum age of the token in seconds (default 1 hour)
    
    Returns:
        Tuple of (old_email, new_email) if token is valid
    
    Raises:
        Exception if token is invalid or expired
    """
    try:
        data = serializer.loads(token, salt="email-change", max_age=max_age)
        old_email, new_email = data.split(":", 1)
        return old_email, new_email
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
                <h2>Hi {_escape_html(username)},</h2>
                <p>Thank you for registering with OmniTrackr! To complete your registration, please verify your email address by clicking the button below:</p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{verification_url}" 
                       style="background-color: #667eea; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                        Verify Email Address
                    </a>
                </div>
                <p>Or copy and paste this link into your browser:</p>
                <p style="word-break: break-all; color: #667eea;">{verification_url}</p>
                <p><strong>This link will expire in 48 hours.</strong></p>
                <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                <p style="color: #666; font-size: 12px;">
                    If you didn't create an account with OmniTrackr, you can safely ignore this email.
                </p>
            </div>
        </body>
    </html>
    """
    
    message = html_message("Verify Your OmniTrackr Email", [email], html)
    
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
                <h2>Hi {_escape_html(username)},</h2>
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
    
    message = html_message("Reset Your OmniTrackr Password", [email], html)
    
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


async def send_email_change_verification_email(new_email: str, username: str, token: str):
    """
    Send email change verification email to new email address.
    
    Args:
        new_email: New email address to verify
        username: User's username
        token: Email change verification token
    """
    verification_url = f"{APP_URL}/?email_change_token={token}&email_change=true"
    
    html = f"""
    <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
                <h1 style="color: white; margin: 0;">Email Change Request</h1>
            </div>
            <div style="padding: 30px; background-color: #f9f9f9;">
                <h2>Hi {_escape_html(username)},</h2>
                <p>You requested to change your OmniTrackr email address to this address. Please verify your new email by clicking the button below:</p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{verification_url}" 
                       style="background-color: #667eea; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                        Verify New Email
                    </a>
                </div>
                <p>Or copy and paste this link into your browser:</p>
                <p style="word-break: break-all; color: #667eea;">{verification_url}</p>
                <p><strong>This link will expire in 1 hour.</strong></p>
                <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                <p style="color: #666; font-size: 12px;">
                    If you didn't request this email change, please contact support immediately.
                </p>
            </div>
        </body>
    </html>
    """
    
    message = html_message("Verify Your New OmniTrackr Email", [new_email], html)
    
    # Only send if email credentials are configured
    if conf.MAIL_USERNAME and conf.MAIL_PASSWORD:
        try:
            import asyncio
            fm = FastMail(conf)
            await asyncio.wait_for(fm.send_message(message), timeout=30.0)
        except asyncio.TimeoutError:
            print(f"ERROR: Email sending timed out after 30 seconds")
            print(f"Failed to send email change verification email to {new_email}")
            print(f"Verification URL (fallback): {verification_url}")
            raise Exception("Email sending timed out. Check your email service configuration.")
        except Exception as e:
            error_msg = str(e)
            print(f"ERROR: Failed to send email change verification email to {new_email}")
            print(f"Error: {error_msg}")
            print(f"Verification URL (fallback): {verification_url}")
            raise Exception(f"Failed to send email: {error_msg}. Check your email service configuration.")
    else:
        # Development mode - just print the verification URL
        print(f"\n{'='*60}")
        print(f"Email Change Verification Required")
        print(f"{'='*60}")
        print(f"To: {new_email}")
        print(f"Username: {username}")
        print(f"Verification URL: {verification_url}")
        print(f"{'='*60}\n")

