"""
Auth endpoints: register, login, logout, me.
Passwords hashed with bcrypt directly (avoids passlib/bcrypt 4+ incompatibility).
Sessions live in Redis (or in-memory fallback).
"""

import logging
import bcrypt
from fastapi import APIRouter, HTTPException, status, Header
from pydantic import BaseModel, EmailStr

from backend.api import state
from backend.auth.session import create_session, delete_session, get_session
from backend.database import create_user, get_user_by_email

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Auth"])


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False


class RegisterRequest(BaseModel):
    email: EmailStr
    name: str
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def _ttl() -> int:
    return state.config.SESSION_TTL_SECONDS if state.config else 604800


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest):
    if get_user_by_email(req.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    user = create_user(email=req.email, name=req.name, password_hash=_hash(req.password))
    token = create_session(state.redis_client, user.id, user.email, user.name, _ttl())
    return {"token": token, "user": {"id": user.id, "email": user.email, "name": user.name}}


@router.post("/login")
async def login(req: LoginRequest):
    user = get_user_by_email(req.email)
    if not user or not _verify(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_session(state.redis_client, user.id, user.email, user.name, _ttl())
    return {"token": token, "user": {"id": user.id, "email": user.email, "name": user.name}}


@router.post("/logout")
async def logout(x_session_token: str = Header(default="")):
    if x_session_token:
        delete_session(state.redis_client, x_session_token)
    return {"status": "logged out"}


@router.get("/me")
async def me(x_session_token: str = Header(default="")):
    if not x_session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = get_session(state.redis_client, x_session_token)
    if not session:
        raise HTTPException(status_code=401, detail="Session expired")
    return session
