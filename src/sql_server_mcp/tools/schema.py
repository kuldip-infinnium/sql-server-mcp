"""Tools: list_tables, get_table_schema, get_table_relationships, search_tables_by_name, get_table_sample_data"""
import json
from ..cache import load_cache
from ..db import run_query


def list_tables(filter: str = "", limit: int = 100) -> str:
    """List all tables with approximate row counts. Optionally filter by name."""
    cache = load_cache()
    if not cache:
        return json.dumps({"error": "Schema cache not available. Try refresh_schema_cache."})

    tables = cache["tables"]
    if filter:
        fl = filter.lower()
        tables = [t for t in tables if fl in t["name"].lower()]

    result = [
        {"schema": t["schema"], "name": t["name"], "row_count_approx": t["row_count_approx"]}
        for t in tables[:limit]
    ]
    return json.dumps({"total_matched": len(tables), "tables": result})


def get_table_schema(table_name: str) -> str:
    """Get full schema for a table: columns, types, PKs, FKs."""
    cache = load_cache()
    if cache:
        matches = [t for t in cache["tables"] if t["name"].lower() == table_name.lower()]
        if matches:
            return json.dumps(matches[0], default=str)

    # DB fallback
    try:
        rows = run_query("""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, CHARACTER_MAXIMUM_LENGTH
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = ?
            ORDER BY ORDINAL_POSITION
        """, [table_name])
        return json.dumps({"table": table_name, "columns": rows})
    except Exception as e:
        return json.dumps({"error": str(e)})


def get_table_relationships(table_name: str) -> str:
    """Get FK relationships for a table — what it references and what references it."""
    cache = load_cache()
    if cache:
        tl = table_name.lower()
        table = next((t for t in cache["tables"] if t["name"].lower() == tl), None)
        if table:
            # What this table depends on (outgoing FKs)
            outgoing = table.get("foreign_keys", [])
            # What depends on this table (incoming FKs from other tables)
            incoming = []
            for t in cache["tables"]:
                for fk in t.get("foreign_keys", []):
                    if fk["ref_table"].lower() == tl:
                        incoming.append({"from_table": t["name"], "via_column": fk["column"], "ref_column": fk["ref_column"]})
            return json.dumps({"table": table_name, "references": outgoing, "referenced_by": incoming})

    return json.dumps({"error": f"Table '{table_name}' not found in cache. Try refresh_schema_cache."})


def search_tables_by_name(keyword: str) -> str:
    """Search tables by keyword. Returns matching table names with row counts."""
    cache = load_cache()
    if not cache:
        return json.dumps({"error": "Schema cache not available."})

    kl = keyword.lower()
    matches = [
        {"schema": t["schema"], "name": t["name"], "row_count_approx": t["row_count_approx"]}
        for t in cache["tables"] if kl in t["name"].lower()
    ]
    return json.dumps({"keyword": keyword, "matches": matches, "count": len(matches)})


def get_table_sample_data(table_name: str, rows: int = 5) -> str:
    """Return top N rows from a table as a data sample."""
    rows = min(rows, 50)  # cap at 50
    try:
        data = run_query(f"SELECT TOP {rows} * FROM [{table_name}]", max_rows=rows)
        return json.dumps({"table": table_name, "sample_rows": data}, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})
