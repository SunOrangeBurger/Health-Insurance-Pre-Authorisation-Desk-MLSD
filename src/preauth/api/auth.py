import asyncio
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from preauth.api.rate_limit import consume_token
from preauth.config import get_settings
from preauth.security import hash_password, token_hash, verify_password
from preauth.store.database import get_session
from preauth.store.models import LoginSession, RunOwner, User

router = APIRouter(prefix="/v1/auth", tags=["authentication"])
COOKIE = "desk_session"
DUMMY_HASH = hash_password(secrets.token_urlsafe(32))


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


async def current_user(request: Request, session: AsyncSession = Depends(get_session)) -> User:
    token = request.cookies.get(COOKIE)
    record = await session.get(LoginSession, token_hash(token)) if token else None
    now = datetime.now(timezone.utc)
    if record is None or record.expires_at.replace(tzinfo=timezone.utc) <= now:
        raise HTTPException(401, "Please sign in")
    user = await session.get(User, record.user_id)
    if user is None or not user.active:
        raise HTTPException(401, "Account unavailable")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if not hmac.compare_digest(request.headers.get("X-CSRF-Token", ""), record.csrf_token):
            raise HTTPException(403, "Invalid CSRF token")
    request.state.login_session = record
    return user


async def hospital_user(user: User = Depends(current_user)) -> User:
    if user.role != "hospital":
        raise HTTPException(403, "Hospital Staff access required")
    return user


async def owned_run(run_id: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> User:
    owner = await session.get(RunOwner, run_id)
    if owner is None or (user.role != "reviewer" and owner.hospital_id != user.hospital_id):
        raise HTTPException(404, "Run not found")
    return user


def public_user(user: User) -> dict:
    return {"id": user.id, "email": user.email, "role": user.role, "hospital_id": user.hospital_id}


@router.post("/login")
async def login(payload: Credentials, request: Request, response: Response, session: AsyncSession = Depends(get_session)):
    # Custom header prevents cross-origin form login; no permissive CORS is installed.
    if request.headers.get("X-Requested-With") != "desk":
        raise HTTPException(403, "Missing login request header")
    key = "login:" + (request.client.host if request.client else "unknown")
    limit = await consume_token(request.app.state.redis, key, 5, 0.1)
    if not limit.allowed:
        raise HTTPException(429, "Too many login attempts", headers={"Retry-After": str(limit.retry_after)})
    user = await session.scalar(select(User).where(User.email == payload.email.strip().lower()))
    valid = await asyncio.to_thread(verify_password, payload.password, user.password_hash if user else DUMMY_HASH)
    if not valid or user is None or not user.active:
        raise HTTPException(401, "Invalid email or password")
    old_token = request.cookies.get(COOKIE)
    if old_token:
        old = await session.get(LoginSession, token_hash(old_token))
        if old:
            await session.delete(old)
    token, csrf = secrets.token_urlsafe(32), secrets.token_hex(32)
    session.add(LoginSession(token_hash=token_hash(token), user_id=user.id, csrf_token=csrf,
                             expires_at=datetime.now(timezone.utc) + timedelta(hours=8)))
    await session.commit()
    response.set_cookie(COOKIE, token, httponly=True, samesite="strict", secure=get_settings().environment == "production", max_age=28800, path="/")
    return {"user": public_user(user), "csrf_token": csrf}


@router.get("/me")
async def me(request: Request, user: User = Depends(current_user)):
    return {"user": public_user(user), "csrf_token": request.state.login_session.csrf_token}


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await session.delete(request.state.login_session)
    await session.commit()
    response.delete_cookie(COOKIE, path="/")
