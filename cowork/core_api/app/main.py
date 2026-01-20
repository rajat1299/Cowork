import pathlib
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SHARED_ROOT = PROJECT_ROOT / "shared"
if str(SHARED_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_ROOT))

from fastapi import FastAPI

from app.api import router as api_router
from app.db import engine
from sqlmodel import SQLModel

app = FastAPI(title="Cowork Core API", version="0.1.0")
app.include_router(api_router)


@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)
