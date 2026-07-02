"""Schema cache: read/write ~/.mcp-cache/<DB_NAME>/schema.json."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

_cache_data: dict | None = None  # in-memory cache for current session


def _cache_dir() -> Path:
    db_name = os.environ.get("DB_NAME", "default")
    base = Path.home() / ".mcp-cache" / db_name
    base.mkdir(parents=True, exist_ok=True)
    return base


def _schema_path() -> Path:
    return _cache_dir() / "schema.json"


def _meta_path() -> Path:
    return _cache_dir() / "schema.meta.json"


def is_cache_valid() -> bool:
    meta = _meta_path()
    if not meta.exists():
        return False
    try:
        data = json.loads(meta.read_text())
        analyzed_at = datetime.fromisoformat(data["analyzed_at"])
        ttl_hours = int(os.environ.get("CACHE_TTL_HOURS", "24"))
        age_hours = (datetime.now(timezone.utc) - analyzed_at).total_seconds() / 3600
        return age_hours < ttl_hours
    except Exception:
        return False


def load_cache() -> dict | None:
    global _cache_data
    if _cache_data is not None:
        return _cache_data
    path = _schema_path()
    if not path.exists():
        return None
    try:
        _cache_data = json.loads(path.read_text(encoding="utf-8"))
        return _cache_data
    except Exception:
        return None


def save_cache(data: dict) -> None:
    global _cache_data
    now = datetime.now(timezone.utc).isoformat()
    data["analyzed_at"] = now
    _schema_path().write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    _meta_path().write_text(json.dumps({"analyzed_at": now}), encoding="utf-8")
    _cache_data = data


def clear_cache() -> None:
    global _cache_data
    _cache_data = None
    for p in [_schema_path(), _meta_path()]:
        if p.exists():
            p.unlink()
