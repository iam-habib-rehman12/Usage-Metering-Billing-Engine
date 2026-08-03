import hashlib
import hmac

from fastapi import Header, HTTPException

from .config import settings


def hash_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def require_admin(x_admin_key: str = Header(default="")) -> None:
    if not settings.admin_api_key or not hmac.compare_digest(
        x_admin_key, settings.admin_api_key
    ):
        raise HTTPException(status_code=401, detail="Invalid admin API key")


def verify_tenant_key(presented: str, stored_hash: str) -> bool:
    return bool(presented) and hmac.compare_digest(hash_key(presented), stored_hash)

