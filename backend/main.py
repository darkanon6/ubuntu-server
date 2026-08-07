from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(title="Server Dashboard")

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
