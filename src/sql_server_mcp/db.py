"""Database connection and safe query execution."""
import json
import os
import re
import time
from pathlib import Path
import pyodbc
from typing import Any

_conn: pyodbc.Connection | None = None

_WRITE_KEYWORDS = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|MERGE|EXEC|EXECUTE)\b",
    re.IGNORECASE,
)
_COMMENT_STRIP = re.compile(r"(--[^\n]*|/\*.*?\*/)", re.DOTALL)

_PREFERRED_DRIVERS = [
    "ODBC Driver 17 for SQL Server",
    "ODBC Driver 18 for SQL Server",
    "SQL Server Native Client 11.0",
    "SQL Server",
]


def _load_credentials() -> dict:
    """Read credentials from env vars first, fall back to ~/.sql-server-mcp.json."""
    creds = {
        "server":   os.environ.get("DB_SERVER", ""),
        "database": os.environ.get("DB_NAME", ""),
        "user":     os.environ.get("DB_USER", ""),
        "password": os.environ.get("DB_PASSWORD", ""),
    }
    if not all(creds.values()):
        config_path = Path.home() / ".sql-server-mcp.json"
        if config_path.exists():
            try:
                saved = json.loads(config_path.read_text(encoding="utf-8"))
                for key in creds:
                    if not creds[key]:
                        creds[key] = saved.get(key, "")
            except Exception:
                pass
    missing = [k for k, v in creds.items() if not v]
    if missing:
        raise RuntimeError(
            f"Missing credentials: {missing}. "
            "Run `sql-server-mcp setup` to configure."
        )
    return creds


def _build_conn_string(driver: str) -> str:
    creds = _load_credentials()
    return (
        f"DRIVER={{{driver}}};SERVER={creds['server']};DATABASE={creds['database']};"
        f"UID={creds['user']};PWD={creds['password']};TrustServerCertificate=yes;"
    )


def get_connection() -> pyodbc.Connection:
    global _conn
    if _conn is not None:
        return _conn

    available = pyodbc.drivers()
    drivers_to_try = [d for d in _PREFERRED_DRIVERS if d in available]
    if not drivers_to_try:
        drivers_to_try = [d for d in available if "SQL" in d]
    if not drivers_to_try:
        raise RuntimeError("No SQL Server ODBC drivers found on this system.")

    last_error = None
    for driver in drivers_to_try:
        for attempt in range(3):
            try:
                _conn = pyodbc.connect(_build_conn_string(driver), autocommit=True, timeout=10)
                return _conn
            except pyodbc.Error as e:
                last_error = e
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))

    raise RuntimeError(f"Could not connect after trying all drivers. Last error: {last_error}")


def reset_connection() -> None:
    global _conn
    if _conn:
        try:
            _conn.close()
        except Exception:
            pass
    _conn = None


def is_write_sql(sql: str) -> bool:
    clean = _COMMENT_STRIP.sub("", sql).strip()
    return bool(_WRITE_KEYWORDS.match(clean))


def run_query(sql: str, params: list | None = None, max_rows: int | None = None) -> list[dict[str, Any]]:
    if is_write_sql(sql):
        raise ValueError("Write operations (INSERT/UPDATE/DELETE/DROP/ALTER/EXEC) are not allowed.")

    limit = max_rows or int(os.environ.get("MAX_ROWS", "200"))
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params or [])
        columns = [col[0] for col in cursor.description]
        rows = []
        for i, row in enumerate(cursor.fetchall()):
            if i >= limit:
                break
            rows.append(dict(zip(columns, row)))
        return rows
    except pyodbc.Error as e:
        reset_connection()
        raise RuntimeError(f"DB error: {e}") from e