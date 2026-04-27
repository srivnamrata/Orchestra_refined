"""
Auth endpoints: register, login, logout, me.
Passwords are hashed with bcrypt. Sessions live in Redis.
"""

import logging
from fastapi import APIRouter, HTTPException, status, Header
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext

from backend.api import state
from backend.auth.session import create_session, delete_session, get_session
from backend.database import create_user, get_user_by_email

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Auth"])

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


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
    user = create_user(
        email=req.email,
        name=req.name,
        password_hash=_pwd.hash(req.password),
    )
    token = create_session(state.redis_client, user.id, user.email, user.name, _ttl())
    return {"token": token, "user": {"id": user.id, "email": user.email, "name": user.name}}


@router.post("/login")
async def login(req: LoginRequest):
    user = get_user_by_email(req.email)
    if not user or not _pwd.verify(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_session(state.redis_client, user.id, user.email, user.name, _ttl())
    return {"token": token, "user": {"id": user.id, "email": user.email, "name": user.name}}


@router.post("/logout")
async def logout(x_session_token: str = Header(default="")):
    if x_session_token and state.redis_client:
        delete_session(state.redis_client, x_session_token)
    return {"status": "logged out"}


@router.get("/me")
async def me(x_session_token: str = Header(default="")):
    if not x_session_token or not state.redis_client:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = get_session(state.redis_client, x_session_token)
    if not session:
        raise HTTPException(status_code=401, detail="Session expired")
    return session
