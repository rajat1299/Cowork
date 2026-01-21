import base64
from pathlib import Path
import time

from app.config import settings


def _resolve_storage_root(path_value: str) -> Path:
    root = Path(path_value)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[1] / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def snapshot_root() -> Path:
    return _resolve_storage_root(settings.snapshot_dir)


def save_snapshot_image(user_id: int, task_id: str, image_base64: str) -> str:
    if "," in image_base64:
        image_base64 = image_base64.split(",", 1)[1]
    root = snapshot_root() / str(user_id) / task_id
    root.mkdir(parents=True, exist_ok=True)
    filename = f"{int(time.time() * 1000)}.jpg"
    file_path = root / filename
    file_path.write_bytes(base64.b64decode(image_base64))
    return str(file_path.relative_to(snapshot_root()))


def resolve_snapshot_path(image_path: str) -> Path:
    root = snapshot_root().resolve()
    candidate = (root / image_path).resolve()
    if root != candidate and root not in candidate.parents:
        raise ValueError("Invalid snapshot path")
    return candidate
