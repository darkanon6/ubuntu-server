import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from backend.routers import auth, containers, system, terminal

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

SESSION_SECRET_KEY = os.environ.get("SESSION_SECRET_KEY")
if not SESSION_SECRET_KEY:
    raise RuntimeError("SESSION_SECRET_KEY must be set in the environment (see .env.example)")

PUBLIC_PATHS = {"/login", "/api/login"}


class AuthGateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in PUBLIC_PATHS or request.session.get("authenticated"):
            return await call_next(request)
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)
        return RedirectResponse(url="/login")


app = FastAPI(title="Server Dashboard")

# Starlette wraps middleware so the *last* one added runs outermost/first.
# AuthGateMiddleware must be added first so SessionMiddleware wraps it and
# populates request.session before AuthGateMiddleware reads it.
app.add_middleware(AuthGateMiddleware)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)

app.include_router(auth.router, prefix="/api")
app.include_router(containers.router, prefix="/api")
app.include_router(system.router, prefix="/api")
app.include_router(terminal.router)


@app.get("/login")
def login_page():
    return FileResponse(FRONTEND_DIR / "login.html")


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
