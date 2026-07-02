"""Tool: run_read_only_sql"""
import json
from ..db import run_query, is_write_sql


def run_read_only_sql(sql: str, row_limit: int = 200) -> str:
    """Execute a read-only SELECT query and return results as JSON."""
    if is_write_sql(sql):
        return json.dumps({"error": "Write operations are not permitted. Only SELECT queries are allowed."})
    try:
        rows = run_query(sql, max_rows=row_limit)
        return json.dumps({"row_count": len(rows), "rows": rows}, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})
