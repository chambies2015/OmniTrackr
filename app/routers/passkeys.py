"""
Passkey settings: list the member's passkeys, add one, rename or remove it.
The sign-in step itself lives in routers/auth.py (/auth/passkey/*).
"""
import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .. import models, passkeys, schemas
from ..dependencies import get_current_user, get_db
from .account import _password_confirmed

router = APIRouter(prefix="/account/passkeys", tags=["account"])

NO_STORE = {"Cache-Control": "no-store"}


def _state(db: Session, user: models.User) -> dict:
    rows = passkeys.passkeys_for(db, user.id)
    return {
        "passkeys": [passkeys.to_public(row) for row in rows],
        "has_password": user.has_password,
        "limit": passkeys.MAX_PASSKEYS_PER_MEMBER,
    }


def _require_password(user: models.User, password: str) -> None:
    if not _password_confirmed(user, password):
        raise HTTPException(status_code=400, detail="That password isn't right.")


def _own_row(db: Session, user: models.User, passkey_id: int) -> models.UserPasskey:
    row = db.query(models.UserPasskey).filter(models.UserPasskey.id == passkey_id,
                                              models.UserPasskey.user_id == user.id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="That passkey is already gone.")
    return row


async def _send_notice(email: str, username: str, added: bool, name: str) -> None:
    try:
        await passkeys.send_change_email(email, username, added, name)
    except Exception as e:  # The change already happened; a missing email never undoes it.
        print(f"Failed to send passkey notice: {e}")


@router.get("")
def list_passkeys(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return JSONResponse(_state(db, current_user), headers=NO_STORE)


@router.post("/options")
def registration_options(payload: schemas.PasskeyPassword, request: Request,
                         current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """What the browser needs to make a passkey. The challenge rides in a short-lived cookie."""
    _require_password(current_user, payload.password)
    rows = passkeys.passkeys_for(db, current_user.id)
    if len(rows) >= passkeys.MAX_PASSKEYS_PER_MEMBER:
        raise HTTPException(status_code=400, detail=f"You can keep up to {passkeys.MAX_PASSKEYS_PER_MEMBER} passkeys. Remove one you no longer use first.")
    challenge = passkeys.new_challenge()
    options = passkeys.registration_options(current_user, rows, challenge, passkeys.rp_id(request))
    response = JSONResponse(options, headers=NO_STORE)
    passkeys.set_challenge_cookie(response, passkeys.challenge_cookie_value("create", challenge, current_user.id),
                                  passkeys.REGISTER_COOKIE_PATH)
    return response


@router.post("/register")
def register(payload: schemas.PasskeyRegistration, request: Request, background_tasks: BackgroundTasks,
             current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Check what the browser made and keep the public half."""
    challenge = passkeys.read_challenge(request.cookies.get(passkeys.CHALLENGE_COOKIE), "create", current_user.id)
    if challenge is None:
        raise HTTPException(status_code=400, detail="That passkey prompt expired. Start again from Add a passkey.")
    rows = passkeys.passkeys_for(db, current_user.id)
    if len(rows) >= passkeys.MAX_PASSKEYS_PER_MEMBER:
        raise HTTPException(status_code=400, detail=f"You can keep up to {passkeys.MAX_PASSKEYS_PER_MEMBER} passkeys. Remove one you no longer use first.")
    try:
        made = passkeys.verify_registration(payload.credential.model_dump(), challenge,
                                            passkeys.rp_id(request), passkeys.expected_origins(request))
    except passkeys.PasskeyError as problem:
        raise HTTPException(status_code=400, detail=str(problem))
    if passkeys.find_by_credential_id(db, made["credential_id"]) is not None:
        raise HTTPException(status_code=400, detail="That passkey is already registered. If it isn't on your list, remove it from the device and make a new one.")

    name = passkeys.clean_name(payload.name) or passkeys.suggested_name(
        made["transports"], made["backed_up"], [row.name for row in rows])
    row = models.UserPasskey(
        user_id=current_user.id,
        credential_id=made["credential_id"],
        public_key=made["public_key"],
        sign_count=made["sign_count"],
        name=name,
        transports=json.dumps(made["transports"]),
        aaguid=made["aaguid"],
        backup_eligible=made["backup_eligible"],
        backed_up=made["backed_up"],
        created_at=passkeys.utcnow(),
    )
    db.add(row)
    db.commit()
    background_tasks.add_task(_send_notice, current_user.email, current_user.username, True, name)
    response = JSONResponse({**_state(db, current_user), "added": passkeys.to_public(row)}, headers=NO_STORE)
    passkeys.clear_challenge_cookie(response, passkeys.REGISTER_COOKIE_PATH)
    return response


@router.post("/{passkey_id}/rename")
def rename(passkey_id: int, payload: schemas.PasskeyRename, request: Request,
           current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = _own_row(db, current_user, passkey_id)
    name = passkeys.clean_name(payload.name)
    if not name:
        raise HTTPException(status_code=400, detail="Give the passkey a name, like the device it lives on.")
    row.name = name
    db.commit()
    return JSONResponse(_state(db, current_user), headers=NO_STORE)


@router.post("/{passkey_id}/remove")
def remove(passkey_id: int, payload: schemas.PasskeyRemove, request: Request, background_tasks: BackgroundTasks,
           current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Forget a passkey. The device still holds its half, which can't open anything on its own."""
    _require_password(current_user, payload.password)
    row = _own_row(db, current_user, passkey_id)
    name = row.name
    db.delete(row)
    db.commit()
    background_tasks.add_task(_send_notice, current_user.email, current_user.username, False, name)
    return JSONResponse(_state(db, current_user), headers=NO_STORE)
