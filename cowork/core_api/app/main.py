import pathlib
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SHARED_ROOT = PROJECT_ROOT / "shared"
if str(SHARED_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router as api_router
from app.config import settings
from app.db import engine
from sqlmodel import SQLModel
from shared.observability import attach_request_logging

app = FastAPI(title="Cowork Core API", version="0.1.0")

# CORS middleware - allow frontend origins
# With allow_credentials=True, methods and headers must be explicit (no "*")
# allow_origin_regex catches localhost on any port (e.g. Vite 5173, 5174)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Alternative dev port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
        "Accept-Language",
        "Content-Language",
        "X-Requested-With",
        "Sec-Fetch-Dest",
        "Sec-Fetch-Mode",
        "Sec-Fetch-Site",
    ],
)

app.include_router(api_router)
attach_request_logging(app, "core_api")


@app.on_event("startup")
def on_startup():
    if settings.auto_create_tables:
        SQLModel.metadata.create_all(engine)
