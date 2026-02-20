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
from shared.observability import attach_request_logging
from app.runtime.deps import maybe_start_auto_install

app = FastAPI(title="Cowork Orchestrator", version="0.1.0")

# CORS middleware - allow frontend origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Alternative dev port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
attach_request_logging(app, "orchestrator")


@app.on_event("startup")
def _maybe_install_deps() -> None:
    maybe_start_auto_install()


@app.on_event("shutdown")
async def _close_http_clients() -> None:
    from app.clients.core_api import close_client
    await close_client()
