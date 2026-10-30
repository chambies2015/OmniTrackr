"""
Two-factor sign-in settings: set up an authenticator app, keep recovery codes,
and turn it off again. The sign-in step itself lives in routers/auth.py.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .. import email as email_utils, models, schemas, two_factor
from ..dependencies import get_current_user, get_db
from .account import _password_confirmed

router = APIRouter(prefix="/account/two-factor", tags=["account"])

NO_STORE = {"Cache-Control": "no-store"}


def _status(user: models.User, row) -> dict:
    enabled = row is not None and row.enabled_at is not None
    return {
        "enabled": enabled,
        "enabled_at": row.enabled_at.isoformat() + "Z" if enabled else None,
        "recovery_codes_left": two_factor.recovery_codes_left(row) if enabled else 0,
        "has_password": user.has_password,
    }


def _require_password(user: models.User, password: str) -> None:
    if not _password_confirmed(user, password):
        raise HTTPException(status_code=400, detail="That password isn't right.")


def _require_enabled(db: Session, user: models.User) -> models.UserTwoFactor:
    row = two_factor.enabled_for(db, user)
    if row is None:
        raise HTTPException(status_code=400, detail="Two-factor sign-in is already off.")
    return row


def _require_code(row: models.UserTwoFactor, code: str) -> str:
    used = two_factor.check_code(row, code)
    if used is None:
        raise HTTPException(status_code=400, detail="That code didn't work. Codes change every 30 seconds, so try the newest one.")
    return used


async def _send_notice(email: str, username: str, turned_on: bool) -> None:
    try:
        await email_utils.send_two_factor_change_email(email, username, turned_on)
    except Exception as e:  # The change already happened; a missing email never undoes it.
        print(f"Failed to send two-factor notice: {e}")


@router.get("")
def two_factor_status(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return JSONResponse(_status(current_user, two_factor.setup_for(db, current_user.id)), headers=NO_STORE)


@router.post("/setup")
def start_setup(payload: schemas.TwoFactorPassword, request: Request, current_user: models.User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    """A fresh secret and QR code. Nothing is switched on until /enable gets a matching code."""
    _require_password(current_user, payload.password)
    row = two_factor.setup_for(db, current_user.id)
    if row is not None and row.enabled_at is not None:
        raise HTTPException(status_code=400, detail="Two-factor sign-in is already on.")
    secret = two_factor.new_secret()
    if row is None:
        row = models.UserTwoFactor(user_id=current_user.id, secret_encrypted="")
        db.add(row)
    row.secret_encrypted = two_factor.encrypt_secret(secret)
    row.last_used_step = None
    row.recovery_codes = None
    db.commit()
    uri = two_factor.otpauth_uri(secret, current_user.email or current_user.username)
    return JSONResponse({
        "secret": two_factor.grouped_secret(secret),
        "otpauth_uri": uri,
        "qr_code": two_factor.qr_data_uri(uri),
    }, headers=NO_STORE)


@router.post("/enable")
def enable(payload: schemas.TwoFactorCode, request: Request, background_tasks: BackgroundTasks,
           current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Switch it on once the app shows a matching code, and hand out the recovery codes once."""
    row = two_factor.setup_for(db, current_user.id)
    if row is None:
        raise HTTPException(status_code=400, detail="Start the setup first.")
    if row.enabled_at is not None:
        raise HTTPException(status_code=400, detail="Two-factor sign-in is already on.")
    if two_factor.check_code(row, payload.code, allow_recovery=False) is None:
        raise HTTPException(status_code=400, detail="That code didn't match. Check that your phone's clock is set automatically, then try the newest code.")
    codes = two_factor.new_recovery_codes()
    now = two_factor.utcnow()
    row.recovery_codes = two_factor.hash_recovery_codes(codes)
    row.recovery_codes_created_at = now
    row.enabled_at = now
    db.commit()
    background_tasks.add_task(_send_notice, current_user.email, current_user.username, True)
    return JSONResponse({**_status(current_user, row), "recovery_codes": codes}, headers=NO_STORE)


@router.post("/recovery-codes")
def new_recovery_codes(payload: schemas.TwoFactorCode, request: Request, current_user: models.User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    """Replace every recovery code with a new set; the old ones stop working."""
    _require_password(current_user, payload.password)
    row = _require_enabled(db, current_user)
    _require_code(row, payload.code)
    codes = two_factor.new_recovery_codes()
    row.recovery_codes = two_factor.hash_recovery_codes(codes)
    row.recovery_codes_created_at = two_factor.utcnow()
    db.commit()
    return JSONResponse({**_status(current_user, row), "recovery_codes": codes}, headers=NO_STORE)


@router.post("/forget-browsers")
def forget_browsers(request: Request, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Every browser that was told to skip the code asks for one again."""
    row = _require_enabled(db, current_user)
    row.trusted_epoch = (row.trusted_epoch or 0) + 1
    db.commit()
    return {"message": "Done. Every browser will ask for a code at the next sign-in."}


@router.post("/disable")
def disable(payload: schemas.TwoFactorCode, request: Request, background_tasks: BackgroundTasks,
            current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_password(current_user, payload.password)
    row = _require_enabled(db, current_user)
    _require_code(row, payload.code)
    db.delete(row)
    db.commit()
    background_tasks.add_task(_send_notice, current_user.email, current_user.username, False)
    return _status(current_user, None)
