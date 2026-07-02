"""Tools: get_db_overview, refresh_schema_cache"""
import json
from datetime import datetime, timezone
from ..cache import load_cache, clear_cache, is_cache_valid
from ..analyzer import analyze_database


def get_db_overview() -> str:
    """Return a high-level summary of the database from cache: counts, modules, largest tables, recently changed SPs."""
    cache = load_cache()
    if not cache:
        return json.dumps({"error": "No schema cache found. The server will analyze on next restart, or call refresh_schema_cache."})

    # Top 10 largest tables
    largest = sorted(cache["tables"], key=lambda t: t["row_count_approx"], reverse=True)[:10]
    largest_summary = [{"name": t["name"], "rows": t["row_count_approx"]} for t in largest]

    # 10 most recently altered SPs
    recent_sps = sorted(
        cache["stored_procedures"],
        key=lambda s: s.get("last_altered", ""),
        reverse=True,
    )[:10]
    recent_summary = [{"name": s["name"], "module": s["module"], "last_altered": s["last_altered"]} for s in recent_sps]

    return json.dumps({
        "db_name": cache.get("db_name"),
        "analyzed_at": cache.get("analyzed_at"),
        "table_count": cache.get("table_count"),
        "sp_count": cache.get("sp_count"),
        "modules": cache.get("modules", []),
        "largest_tables": largest_summary,
        "recently_modified_sps": recent_summary,
    }, default=str)


def refresh_schema_cache() -> str:
    """Force re-analyze the database and rebuild the schema cache."""
    try:
        clear_cache()
        data = analyze_database()
        return json.dumps({
            "message": "Schema cache refreshed successfully.",
            "db_name": data["db_name"],
            "table_count": data["table_count"],
            "sp_count": data["sp_count"],
            "modules": data["modules"],
            "analyzed_at": data.get("analyzed_at"),
        })
    except Exception as e:
        return json.dumps({"error": str(e)})
