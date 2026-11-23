"""
Email utilities for OmniTrackr.
Handles sending verification and password reset emails.
"""
import asyncio
import hashlib
import hmac
import os
import secrets
from html import escape as _escape_html, unescape as _unescape_html
from typing import List
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from fastapi_mail.schemas import MultipartSubtypeEnum
from itsdangerous import URLSafeTimedSerializer
from dotenv import load_dotenv
from .auth import SECRET_KEY

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
serializer = URLSafeTimedSerializer(SECRET_KEY)

# Base URL for the application
APP_URL = os.getenv("APP_URL", "http://localhost:8000")
# New-account verification links stay valid for 48 hours (people often open them the next day).
VERIFICATION_MAX_AGE = 48 * 3600


class _TextExtractor:
    """A monotonic HTML lexer for our mail's readable text alternative.

    HTMLParser repeatedly searches the remaining input for an unfinished tag,
    making malformed tag sequences quadratic. Here every scan advances its
    cursor, and incomplete tags are emitted as text without buffering/retrying.
    """

    BLOCK_TAGS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "li", "table"}
    RAW_TAGS = {"script", "style"}
    SPACE = " \t\n\r\f"

    def __init__(self):
        self.parts: list[str] = []
        self.head_depth = 0
        self.raw_tag: str | None = None
        self.link_href: str | None = None
        self.link_text: list[str] = []

    @staticmethod
    def _tag_end(html: str, cursor: int) -> tuple[int, bool]:
        """Stop at a terminator or a fresh unquoted '<'; never rescan a prefix."""
        quote = None
        while cursor < len(html):
            char = html[cursor]
            if quote is not None:
                if char == quote:
                    quote = None
            elif char in "\"'":
                quote = char
            elif char == ">":
                return cursor + 1, True
            elif char == "<":
                return cursor, False
            cursor += 1
        return cursor, False

    def _href(self, html: str, cursor: int, end: int) -> str | None:
        """Read only href; discarded attributes need no allocation or decoding."""
        href = None
        while cursor < end:
            while cursor < end and html[cursor] in self.SPACE + "/":
                cursor += 1
            name_start = cursor
            while cursor < end and html[cursor] not in self.SPACE + "=/":
                cursor += 1
            is_href = cursor - name_start == 4 and html[name_start:cursor].lower() == "href"
            while cursor < end and html[cursor] in self.SPACE:
                cursor += 1
            if cursor >= end or html[cursor] != "=":
                if is_href:
                    href = None
                continue
            cursor += 1
            while cursor < end and html[cursor] in self.SPACE:
                cursor += 1
            quote = html[cursor] if cursor < end and html[cursor] in "\"'" else None
            if quote:
                cursor += 1
            value_start = cursor
            if quote:
                while cursor < end and html[cursor] != quote:
                    cursor += 1
            else:
                while cursor < end and html[cursor] not in self.SPACE:
                    cursor += 1
            if is_href:
                href = _unescape_html(html[value_start:cursor])
            if quote and cursor < end:
                cursor += 1
        return href

    def _append(self, text: str):
        if not self.head_depth and not self.raw_tag:
            (self.link_text if self.link_href is not None else self.parts).append(text)

    def _flush_link(self):
        if self.link_href is not None:
            label = " ".join("".join(self.link_text).split())
            self.parts.append(f"{label} ({self.link_href})" if label and self.link_href else label or self.link_href)
            self.link_href, self.link_text = None, []

    def feed(self, html: str):
        cursor = 0
        size = len(html)
        while cursor < size:
            opening = html.find("<", cursor)
            if opening == -1:
                self._append(_unescape_html(html[cursor:]))
                break
            self._append(_unescape_html(html[cursor:opening]))
            if self.raw_tag:
                name_end = opening + 2 + len(self.raw_tag)
                if (html[opening:opening + 2] != "</"
                        or html[opening + 2:name_end].lower() != self.raw_tag
                        or (name_end < size and html[name_end] not in self.SPACE + "/>")):
                    cursor = opening + 1
                    continue
            if html.startswith("<!--", opening):
                comment_end = html.find("-->", opening + 4)
                cursor = size if comment_end == -1 else comment_end + 3
                continue
            if html.startswith(("<!", "<?"), opening):
                cursor, _ = self._tag_end(html, opening + 2)
                continue
            closing = html.startswith("</", opening)
            name_start = opening + (2 if closing else 1)
            if name_start >= size or not ("a" <= html[name_start].lower() <= "z"):
                self._append("<")
                cursor = opening + 1
                continue
            name_end = name_start
            while name_end < size and html[name_end] not in self.SPACE + "/><":
                name_end += 1
            end, complete = self._tag_end(html, name_end)
            if not complete:
                self._append(_unescape_html(html[opening:end]))
                cursor = end
                continue
            # Only our recognized tags are short, so a huge name stays unallocated.
            tag = html[name_start:name_end].lower() if name_end - name_start <= 6 else ""
            if closing:
                self._end_tag(tag)
            else:
                self._start_tag(tag, html, name_end, end - 1)
                if html[end - 2] == "/":
                    self._end_tag(tag)
            cursor = end

    def _start_tag(self, tag: str, html: str, attrs_start: int, attrs_end: int):
        if tag == "head":
            self.head_depth += 1
        elif tag in self.RAW_TAGS:
            self.raw_tag = tag
        elif self.head_depth:
            return
        elif tag == "br":
            self._append("\n")
        elif tag == "a":
            self._flush_link()
            self.link_href = self._href(html, attrs_start, attrs_end)

    def _end_tag(self, tag: str):
        if tag == self.raw_tag:
            self.raw_tag = None
        elif tag == "head":
            self.head_depth = max(0, self.head_depth - 1)
        elif not self.head_depth:
            if tag == "a":
                self._flush_link()
            elif tag in self.BLOCK_TAGS:
                self._append("\n")

    def close(self):
        # A malformed or unclosed link must not silently discard readable text.
        self._flush_link()


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
    return serializer.dumps({"email": email, "nonce": secrets.token_urlsafe(24)}, salt="email-verification")


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
        if isinstance(email, dict):
            email = email.get("email")
        if not isinstance(email, str) or not email:
            raise ValueError("Invalid email token payload")
        return email
    except Exception:
        raise


def generate_reset_token(email: str) -> str:
    """Generate a secure token for password reset."""
    return serializer.dumps({"email": email, "nonce": secrets.token_urlsafe(24)}, salt="password-reset")


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
        if isinstance(email, dict):
            email = email.get("email")
        if not isinstance(email, str) or not email:
            raise ValueError("Invalid email token payload")
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


def signup_code(token: str) -> str:
    """The 6-digit code that goes with one verification link (Nov 2026).

    Typing it on the sign-up card confirms the address without leaving the tab, which
    matters on phones, where the mail app opens links in its own browser (not signed
    in, and without the titles a guest saved). It is derived from the stored token,
    so it needs no column of its own and a new email (a new token) replaces it.
    """
    digest = hmac.new(SECRET_KEY.encode("utf-8"), f"omnitrackr-signup-code:{token}".encode("utf-8"), hashlib.sha256).digest()
    return f"{int.from_bytes(digest[:8], 'big') % 1_000_000:06d}"


def verification_email_html(username: str, code: str, verification_url: str) -> str:
    """The confirm-your-email message: the code first, then the one-tap link."""
    spaced = f"{code[:3]} {code[3:]}"
    return f"""
    <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #1f2333;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 26px 30px; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 24px;">Confirm your email</h1>
            </div>
            <div style="padding: 30px; background-color: #f9f9f9;">
                <p style="margin-top: 0;">Hi {_escape_html(username)},</p>
                <p>Type this code on the OmniTrackr sign-up screen to open your library:</p>
                <p style="font-size: 34px; font-weight: bold; letter-spacing: 6px; text-align: center; margin: 26px 0; color: #4c3bb5; font-family: 'Courier New', monospace;">{spaced}</p>
                <p>Or confirm with one tap:</p>
                <div style="text-align: center; margin: 24px 0;">
                    <a href="{verification_url}"
                       style="background-color: #667eea; color: white; padding: 14px 28px; text-decoration: none; border-radius: 999px; display: inline-block; font-weight: bold;">
                        Confirm my email
                    </a>
                </div>
                <p style="color: #555; font-size: 14px;">Tap the button on the device you signed up on and you go straight into your library. The code and the button work for 48 hours.</p>
                <p style="color: #555; font-size: 13px;">If the button doesn't work, copy this link into your browser:</p>
                <p style="word-break: break-all; color: #667eea; font-size: 13px;">{verification_url}</p>
                <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                <p style="color: #666; font-size: 12px;">
                    If you didn't sign up for OmniTrackr, you can ignore this email. No account opens without this code or link.
                </p>
            </div>
        </body>
    </html>
    """


async def _deliver_credential_email(message: MessageSchema) -> bool:
    """Send credentials only to the mailbox. SMTP errors may contain message content."""
    if not (conf.MAIL_USERNAME and conf.MAIL_PASSWORD):
        print("Credential email delivery skipped because SMTP is not configured.")
        return False
    try:
        await asyncio.wait_for(FastMail(conf).send_message(message), timeout=30.0)
    except Exception:
        raise RuntimeError("Credential email delivery failed. Check SMTP configuration.") from None
    return True


async def send_verification_email(email: str, username: str, token: str):
    """
    Send the confirm-your-email message to a new member: a 6-digit code and a link.

    Args:
        email: User's email address
        username: User's username
        token: Verification token (the code is derived from it, see signup_code)
    """
    verification_url = f"{APP_URL}/?token={token}&email_verified=true"
    code = signup_code(token)
    html = verification_email_html(username, code, verification_url)

    # The code leads the subject, so a phone's notification shows it without opening the mail.
    message = html_message(f"{code} is your OmniTrackr code", [email], html)
    
    return await _deliver_credential_email(message)


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
    
    return await _deliver_credential_email(message)


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
    
    return await _deliver_credential_email(message)


async def send_two_factor_change_email(email: str, username: str, turned_on: bool):
    """Tell the member two-factor sign-in was switched on or off, in case it wasn't them."""
    settings_url = f"{APP_URL}/#settings-signin"
    if turned_on:
        subject = "Two-factor sign-in is on for your OmniTrackr account"
        headline = "Two-factor sign-in is on"
        body = ("From now on, logging in asks for a code from your authenticator app after your password. "
                "Keep your recovery codes somewhere safe. Each one gets you in once if you lose your phone.")
    else:
        subject = "Two-factor sign-in is off for your OmniTrackr account"
        headline = "Two-factor sign-in is off"
        body = "Logging in now only needs your password (or Google). You can turn codes back on in Settings at any time."

    html = f"""
    <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
                <h1 style="color: white; margin: 0;">{headline}</h1>
            </div>
            <div style="padding: 30px; background-color: #f9f9f9;">
                <h2>Hi {_escape_html(username)},</h2>
                <p>{body}</p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{settings_url}"
                       style="background-color: #667eea; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                        Open sign-in settings
                    </a>
                </div>
                <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                <p style="color: #666; font-size: 12px;">
                    If you didn't make this change, reset your password right away and email omnitrackr@gmail.com.
                </p>
            </div>
        </body>
    </html>
    """

    message = html_message(subject, [email], html)
    if conf.MAIL_USERNAME and conf.MAIL_PASSWORD:
        import asyncio
        fm = FastMail(conf)
        await asyncio.wait_for(fm.send_message(message), timeout=30.0)
    else:
        print(f"INFO: Two-factor {'enabled' if turned_on else 'disabled'} notice for {email} (email not configured)")


async def send_security_notice_email(email: str, username: str, subject: str, headline: str, body: str):
    """Tell a member their password or sign-in email just changed, in case it wasn't them.

    Sent to the address the account had before the change, so someone who took
    over a session can't hide it by moving the email first.
    """
    reset_url = f"{APP_URL}/#landing-auth"
    html = f"""
    <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
                <h1 style="color: white; margin: 0;">{_escape_html(headline)}</h1>
            </div>
            <div style="padding: 30px; background-color: #f9f9f9;">
                <h2>Hi {_escape_html(username)},</h2>
                <p>{_escape_html(body)}</p>
                <p>If this was you, there's nothing else to do.</p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_url}"
                       style="background-color: #667eea; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                        Open OmniTrackr
                    </a>
                </div>
                <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                <p style="color: #666; font-size: 12px;">
                    If you didn't make this change, use "Forgot password" on the log-in form right away and email omnitrackr@gmail.com so we can help.
                </p>
            </div>
        </body>
    </html>
    """

    message = html_message(subject, [email], html)
    if conf.MAIL_USERNAME and conf.MAIL_PASSWORD:
        import asyncio
        fm = FastMail(conf)
        await asyncio.wait_for(fm.send_message(message), timeout=30.0)
    else:
        print(f"INFO: Security notice ({headline}) for {email} (email not configured)")


async def send_security_notice_quietly(email: str, username: str, subject: str, headline: str, body: str) -> None:
    """Background-task wrapper: the change already happened, so a failed email never undoes it."""
    if not email:
        return
    try:
        await send_security_notice_email(email, username, subject, headline, body)
    except Exception as e:
        print(f"Failed to send security notice: {e}")


PASSWORD_CHANGED_NOTICE = (
    "Your OmniTrackr password was changed",
    "Your password was changed",
    "The password for your OmniTrackr account was just changed. Every other browser and phone that was "
    "signed in has been signed out.",
)
PASSWORD_RESET_NOTICE = (
    "Your OmniTrackr password was reset",
    "Your password was reset",
    "The password for your OmniTrackr account was just reset with a link sent to this address. Every "
    "browser and phone that was signed in has been signed out.",
)


def email_changed_notice(new_email: str) -> tuple[str, str, str]:
    return (
        "Your OmniTrackr sign-in email was changed",
        "Your sign-in email was changed",
        f"Your OmniTrackr account now signs in with {new_email}. Emails from OmniTrackr will go there from now on, "
        "and this address will no longer get them.",
    )


async def send_kofi_claim_email(email: str, username: str, confirm_url: str):
    """Ask the owner of a Ko-fi email to confirm that a payment from it belongs to this OmniTrackr account."""
    html = f"""
    <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
                <h1 style="color: white; margin: 0;">Link your Ko-fi support</h1>
            </div>
            <div style="padding: 30px; background-color: #f9f9f9;">
                <p>Hi,</p>
                <p>The OmniTrackr member <strong>@{_escape_html(username)}</strong> asked to link a Ko-fi payment made with
                this email address to their account. If that's you, press the button and your supporter perks switch on.</p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{confirm_url}"
                       style="background-color: #667eea; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                        Link my Ko-fi payment
                    </a>
                </div>
                <p>Or copy and paste this link into your browser:</p>
                <p style="word-break: break-all; color: #667eea;">{confirm_url}</p>
                <p>The link works for 3 days.</p>
                <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                <p style="color: #666; font-size: 12px;">
                    If you didn't ask for this, ignore this email and nothing changes.
                </p>
            </div>
        </body>
    </html>
    """

    message = html_message("Link your Ko-fi support to OmniTrackr", [email], html)
    await _deliver_credential_email(message)


def gift_email_html(gifts: list, resend: bool = False) -> str:
    """The Ko-fi gift email: each gift's link to pass on, its code, and the giver's own link for the card."""
    blocks = []
    for gift in gifts:
        url = _escape_html(gift["url"])
        manage = _escape_html(gift["manage_url"])
        status = ("Opened already." if gift.get("state") == "opened"
                  else "Not opened yet.") if resend else ""
        blocks.append(f"""
                <div style="background: #ffffff; border: 1px solid #e4e1f5; border-radius: 12px; padding: 20px; margin: 20px 0;">
                    <p style="margin: 0 0 6px; font-size: 18px;"><strong>{_escape_html(gift["months_label"].capitalize())} of supporter perks</strong></p>
                    <p style="margin: 0 0 14px; color: #555;">Gift code <strong style="letter-spacing: 1px;">{_escape_html(gift["code"])}</strong>{f" · {status}" if status else ""}</p>
                    <p style="margin: 0 0 8px;">The link to send:</p>
                    <p style="word-break: break-all; margin: 0 0 16px;"><a href="{url}" style="color: #5b3fd6;">{url}</a></p>
                    <a href="{manage}" style="background-color: #667eea; color: white; padding: 12px 22px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">Write the card or print it</a>
                </div>""")
    lead = ("Here are the gifts bought from this Ko-fi email." if resend else
            "Thank you for buying an OmniTrackr gift on Ko-fi. It's ready to give.")
    html = f"""
    <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
                <h1 style="color: white; margin: 0;">Your gift is ready</h1>
            </div>
            <div style="padding: 30px; background-color: #f9f9f9;">
                <p>Hi,</p>
                <p>{lead} Send the link to the person it's for, or print the card and give it in person.
                They open it with a free OmniTrackr account, and the perks start the day they do.</p>
                {"".join(blocks)}
                <p>The "Write the card" button is just for you. It lets you add who the gift is for, who it's from and a short
                note, print a card with the code on it, and see when it's been opened. Keep that one to yourself.</p>
                <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                <p style="color: #666; font-size: 12px;">
                    You're getting this because a Ko-fi payment to OmniTrackr with OT-GIFT in its message came from this
                    address. If that wasn't you, reply and we'll sort it out.
                </p>
            </div>
        </body>
    </html>
    """
    return html


async def send_gift_email(email: str, gifts: list, resend: bool = False) -> bool:
    """Send a Ko-fi gift's links to the address that paid for it."""
    if not gifts:
        return False
    subject = "Your OmniTrackr gift links" if resend else "Your OmniTrackr gift is ready to give"
    message = html_message(subject, [email], gift_email_html(gifts, resend=resend))
    return await _deliver_credential_email(message)
