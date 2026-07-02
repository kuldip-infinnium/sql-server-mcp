"""Tools: list_stored_procedures, search_sps_by_name, get_sp_definition, execute_sp"""
import json
import re
from ..cache import load_cache
from ..db import run_query, is_write_sql, get_connection


_WRITE_IN_BODY = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|MERGE)\b",
    re.IGNORECASE,
)


def list_stored_procedures(filter: str = "", module: str = "", limit: int = 100) -> str:
    """List stored procedures. Optionally filter by name keyword or module prefix."""
    cache = load_cache()
    if not cache:
        return json.dumps({"error": "Schema cache not available."})

    sps = cache["stored_procedures"]
    if filter:
        fl = filter.lower()
        sps = [s for s in sps if fl in s["name"].lower()]
    if module:
        ml = module.lower()
        sps = [s for s in sps if s["module"].lower() == ml]

    result = [
        {"name": s["name"], "module": s["module"], "last_altered": s["last_altered"]}
        for s in sps[:limit]
    ]
    return json.dumps({"total_matched": len(sps), "stored_procedures": result})


def search_sps_by_name(keyword: str) -> str:
    """Search stored procedures by keyword in name."""
    cache = load_cache()
    if not cache:
        return json.dumps({"error": "Schema cache not available."})

    kl = keyword.lower()
    matches = [
        {"name": s["name"], "module": s["module"], "last_altered": s["last_altered"]}
        for s in cache["stored_procedures"] if kl in s["name"].lower()
    ]
    return json.dumps({"keyword": keyword, "matches": matches, "count": len(matches)})


def get_sp_definition(sp_name: str) -> str:
    """Return the full SQL definition of a stored procedure."""
    try:
        rows = run_query(
            "SELECT definition FROM sys.sql_modules WHERE object_id = OBJECT_ID(?)",
            [sp_name],
            max_rows=1,
        )
        if not rows:
            return json.dumps({"error": f"SP '{sp_name}' not found or definition is encrypted."})
        return json.dumps({"sp_name": sp_name, "definition": rows[0]["definition"]})
    except Exception as e:
        return json.dumps({"error": str(e)})


def execute_sp(sp_name: str, params: dict | None = None) -> str:
    """Execute a stored procedure (read-only). Rejects SPs with write operations in their body."""
    # Safety: check SP body for write keywords before running
    defn_result = json.loads(get_sp_definition(sp_name))
    if "error" in defn_result:
        return json.dumps(defn_result)

    body = defn_result.get("definition", "")
    if _WRITE_IN_BODY.search(body):
        return json.dumps({
            "error": f"SP '{sp_name}' contains write operations and cannot be executed in read-only mode."
        })

    try:
        conn = get_connection()
        cursor = conn.cursor()
        if params:
            param_str = ", ".join(f"@{k}=?" for k in params)
            cursor.execute(f"EXEC {sp_name} {param_str}", list(params.values()))
        else:
            cursor.execute(f"EXEC {sp_name}")

        if cursor.description:
            columns = [col[0] for col in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchmany(200)]
            return json.dumps({"sp_name": sp_name, "row_count": len(rows), "rows": rows}, default=str)
        return json.dumps({"sp_name": sp_name, "message": "Executed successfully, no rows returned."})
    except Exception as e:
        return json.dumps({"error": str(e)})
