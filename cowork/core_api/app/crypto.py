import json

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def _get_fernet() -> Fernet:
    key = settings.data_encryption_key
    if not key:
        raise RuntimeError("DATA_ENCRYPTION_KEY is not configured")
    return Fernet(key)


def encrypt_json(value: dict) -> dict:
    token = _get_fernet().encrypt(json.dumps(value).encode("utf-8"))
    return {"ciphertext": token.decode("utf-8")}


def decrypt_json(value: dict | None) -> dict | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        return None
    token = value.get("ciphertext")
    if not token:
        return value
    try:
        raw = _get_fernet().decrypt(token.encode("utf-8"))
    except InvalidToken as exc:
        raise ValueError("Failed to decrypt extra params") from exc
    return json.loads(raw.decode("utf-8"))
