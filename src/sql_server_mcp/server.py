"""MCP Server using FastMCP — registers all tools and prompts."""
from mcp.server.fastmcp import FastMCP

from .cache import is_cache_valid, load_cache
from .analyzer import analyze_database
from .tools.query import run_read_only_sql as _run_sql
from .tools.schema import (
    list_tables as _list_tables,
    get_table_schema as _get_table_schema,
    get_table_relationships as _get_table_relationships,
    search_tables_by_name as _search_tables,
    get_table_sample_data as _sample_data,
)
from .tools.procedures import (
    list_stored_procedures as _list_sps,
    search_sps_by_name as _search_sps,
    get_sp_definition as _sp_def,
    execute_sp as _exec_sp,
)
from .tools.overview import get_db_overview as _overview, refresh_schema_cache as _refresh
from .prompts.definitions import (
    prompt_explore_database,
    prompt_find_sp_for_feature,
    prompt_explain_table,
    prompt_write_query_for,
    prompt_sp_audit,
)

app = FastMCP("sql-server-mcp")

# ── Tools ──────────────────────────────────────────────────────────────────

@app.tool()
def get_db_overview() -> str:
    """High-level DB summary: table/SP counts, modules, largest tables, recently modified SPs."""
    return _overview()


@app.tool()
def run_read_only_sql(sql: str, row_limit: int = 200) -> str:
    """Execute a SELECT query against the database. Write operations are blocked."""
    return _run_sql(sql, row_limit)


@app.tool()
def list_tables(filter: str = "", limit: int = 100) -> str:
    """List all tables with approximate row counts. Optionally filter by name keyword."""
    return _list_tables(filter, limit)


@app.tool()
def get_table_schema(table_name: str) -> str:
    """Get columns, data types, primary keys, and foreign keys for a table."""
    return _get_table_schema(table_name)


@app.tool()
def get_table_relationships(table_name: str) -> str:
    """Get FK relationships: what this table references and what other tables reference it."""
    return _get_table_relationships(table_name)


@app.tool()
def search_tables_by_name(keyword: str) -> str:
    """Search for tables by keyword in their name."""
    return _search_tables(keyword)


@app.tool()
def get_table_sample_data(table_name: str, rows: int = 5) -> str:
    """Get a sample of top N rows from a table (max 50)."""
    return _sample_data(table_name, rows)


@app.tool()
def list_stored_procedures(filter: str = "", module: str = "", limit: int = 100) -> str:
    """List stored procedures with created/altered dates. Filter by name keyword or module."""
    return _list_sps(filter, module, limit)


@app.tool()
def search_sps_by_name(keyword: str) -> str:
    """Search stored procedures by keyword in their name."""
    return _search_sps(keyword)


@app.tool()
def get_sp_definition(sp_name: str) -> str:
    """Get the full SQL definition of a stored procedure."""
    return _sp_def(sp_name)


@app.tool()
def execute_sp(sp_name: str, params: dict | None = None) -> str:
    """Execute a stored procedure. Blocked if the SP body contains write operations."""
    return _exec_sp(sp_name, params)


@app.tool()
def refresh_schema_cache() -> str:
    """Force re-analyze the database and rebuild the local schema cache."""
    return _refresh()


# ── Prompts ────────────────────────────────────────────────────────────────

@app.prompt()
def explore_database() -> str:
    """Get a high-level overview of the connected database."""
    return prompt_explore_database()


@app.prompt()
def find_sp_for_feature(feature: str) -> str:
    """Find stored procedures related to a feature or keyword."""
    return prompt_find_sp_for_feature(feature)


@app.prompt()
def explain_table(table_name: str) -> str:
    """Get a full explanation of a table's structure and relationships."""
    return prompt_explain_table(table_name)


@app.prompt()
def write_query_for(goal: str) -> str:
    """Help write a SQL query for a given goal."""
    return prompt_write_query_for(goal)


@app.prompt()
def sp_audit(days: int = 7) -> str:
    """List stored procedures modified in the last N days."""
    return prompt_sp_audit(days)


# ── Startup ────────────────────────────────────────────────────────────────

def _init_cache() -> None:
    if is_cache_valid():
        load_cache()
    else:
        try:
            analyze_database()
        except Exception as e:
            print(f"[sql-server-mcp] Warning: DB analysis failed at startup: {e}")


def main() -> None:
    _init_cache()
    app.run(transport="stdio")
