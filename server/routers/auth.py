"""Sign in / out and access status for the studio (see server/auth.py)."""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from .. import auth

router = APIRouter(tags=["auth"])

_attempts: dict[str, list[float]] = defaultdict(list)
MAX_ATTEMPTS = 10  # per client per 10 minutes


class LoginIn(BaseModel):
    password: str


@router.get("/auth/status")
def status(request: Request) -> dict:
    required = bool(auth.password())
    authed = auth.valid(request.cookies.get(auth.COOKIE)) if required else auth.client_is_local(
        request.client.host if request.client else None, request.headers.get("x-forwarded-for"))
    return {"password_required": required, "signed_in": authed}


@router.post("/auth/login")
def login(body: LoginIn, request: Request, response: Response) -> dict:
    if not auth.password():
        raise HTTPException(400, "No password is set for this studio.")
    who = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "?")).split(",")[0]
    now = time.time()
    _attempts[who] = [t for t in _attempts[who] if now - t < 600]
    if len(_attempts[who]) >= MAX_ATTEMPTS:
        raise HTTPException(429, "Too many attempts. Wait a few minutes.")
    _attempts[who].append(now)
    if not auth.check_password(body.password):
        raise HTTPException(401, "That password isn't right.")
    secure = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    response.set_cookie(auth.COOKIE, auth.issue(), max_age=auth.SESSION_DAYS * 86400, httponly=True,
                        samesite="lax", secure=secure, path="/")
    return {"signed_in": True}


@router.post("/auth/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(auth.COOKIE, path="/")
    return {"signed_in": False}
