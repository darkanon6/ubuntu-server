import os
import secrets

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(payload: LoginRequest, request: Request):
    expected_username = os.environ.get("DASHBOARD_USERNAME")
    expected_password = os.environ.get("DASHBOARD_PASSWORD")
    if not expected_username or not expected_password:
        raise HTTPException(status_code=500, detail="Dashboard credentials are not configured")

    username_ok = secrets.compare_digest(payload.username, expected_username)
    password_ok = secrets.compare_digest(payload.password, expected_password)
    if not (username_ok and password_ok):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    request.session["authenticated"] = True
    return {"ok": True}


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}
