"""MCP Prompt definitions — pre-built conversation starters with injected schema context."""
import json
from ..cache import load_cache


def _overview_context() -> str:
    cache = load_cache()
    if not cache:
        return "Schema cache not available. Call refresh_schema_cache first."
    return json.dumps({
        "db_name": cache.get("db_name"),
        "table_count": cache.get("table_count"),
        "sp_count": cache.get("sp_count"),
        "modules": cache.get("modules", []),
    })


def prompt_explore_database() -> str:
    """Prompt: Explore this database — injects full overview + module list."""
    cache = load_cache()
    if not cache:
        return "No schema cache available. Please wait for startup analysis or call refresh_schema_cache."

    modules = cache.get("modules", [])
    largest = sorted(cache["tables"], key=lambda t: t["row_count_approx"], reverse=True)[:10]

    return (
        f"You are connected to the **{cache['db_name']}** SQL Server database.\n\n"
        f"**Summary:**\n"
        f"- {cache['table_count']} tables\n"
        f"- {cache['sp_count']} stored procedures\n"
        f"- Detected modules: {', '.join(modules)}\n\n"
        f"**Largest tables:**\n" +
        "\n".join(f"- {t['name']}: ~{t['row_count_approx']:,} rows" for t in largest) +
        "\n\nUse tools like `list_tables`, `get_table_schema`, `search_sps_by_name`, and `run_read_only_sql` to explore further."
    )


def prompt_find_sp_for_feature(feature: str) -> str:
    """Prompt: Find SPs related to a feature — filters by keyword."""
    cache = load_cache()
    if not cache:
        return "Schema cache not available."

    kl = feature.lower()
    matches = [s for s in cache["stored_procedures"] if kl in s["name"].lower()]

    if not matches:
        return f"No stored procedures found matching '{feature}'. Try a broader keyword or use `list_stored_procedures`."

    sp_list = "\n".join(
        f"- `{s['name']}` (module: {s['module']}, last changed: {s['last_altered']})"
        for s in matches[:20]
    )
    return (
        f"Found **{len(matches)}** stored procedures related to **'{feature}'**:\n\n"
        f"{sp_list}\n\n"
        f"Use `get_sp_definition('<sp_name>')` to see the full SQL for any of these."
    )


def prompt_explain_table(table_name: str) -> str:
    """Prompt: Explain a table — injects schema + relationships."""
    cache = load_cache()
    if not cache:
        return "Schema cache not available."

    tl = table_name.lower()
    table = next((t for t in cache["tables"] if t["name"].lower() == tl), None)
    if not table:
        return f"Table '{table_name}' not found. Use `list_tables` to browse available tables."

    cols = "\n".join(
        "  - {name} ({type}){null}{pk}".format(
            name=c["name"],
            type=c["type"],
            null="" if c["nullable"] else " NOT NULL",
            pk=" PK" if c["name"] in table.get("primary_keys", []) else "",
        )
        for c in table.get("columns", [])[:30]
    )
    fks = table.get("foreign_keys", [])
    fk_text = "\n".join(f"  - {fk['column']} → {fk['ref_table']}.{fk['ref_column']}" for fk in fks) or "  None"

    incoming = []
    for t in cache["tables"]:
        for fk in t.get("foreign_keys", []):
            if fk["ref_table"].lower() == tl:
                incoming.append(f"  - {t['name']}.{fk['column']} → {fk['ref_column']}")
    incoming_text = "\n".join(incoming[:10]) or "  None"

    return (
        f"## Table: `{table['name']}` (schema: {table['schema']})\n"
        f"~{table['row_count_approx']:,} rows\n\n"
        f"**Columns:**\n{cols}\n\n"
        f"**References (outgoing FK):**\n{fk_text}\n\n"
        f"**Referenced by (incoming FK):**\n{incoming_text}\n\n"
        f"Use `get_table_sample_data('{table_name}')` to see example rows."
    )


def prompt_write_query_for(goal: str) -> str:
    """Prompt: Write a SQL query — injects relevant table schemas based on goal keywords."""
    cache = load_cache()
    if not cache:
        return "Schema cache not available."

    words = [w.lower() for w in goal.split() if len(w) > 3]
    relevant = []
    for t in cache["tables"]:
        if any(w in t["name"].lower() for w in words):
            relevant.append(t)
    relevant = relevant[:5]

    if not relevant:
        return (
            f"Goal: **{goal}**\n\n"
            "No tables matched your goal keywords automatically. "
            "Use `search_tables_by_name` to find relevant tables, then I can help write the query."
        )

    schemas = "\n\n".join(
        f"**{t['name']}** (~{t['row_count_approx']:,} rows)\n"
        + "Columns: " + ", ".join(f"{c['name']} ({c['type']})" for c in t.get("columns", [])[:15])
        for t in relevant
    )
    return (
        f"**Goal:** {goal}\n\n"
        f"**Relevant tables found:**\n\n{schemas}\n\n"
        "Based on these schemas, here's a starting query — adjust as needed."
    )


def prompt_sp_audit(days: int = 7) -> str:
    """Prompt: Audit recently modified SPs — shows SPs changed in the last N days."""
    cache = load_cache()
    if not cache:
        return "Schema cache not available."

    from datetime import datetime, timedelta, timezone
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    recent = [
        s for s in cache["stored_procedures"]
        if s.get("last_altered", "") >= cutoff[:10]
    ]
    recent_sorted = sorted(recent, key=lambda s: s.get("last_altered", ""), reverse=True)

    if not recent_sorted:
        return f"No stored procedures were modified in the last {days} days."

    sp_list = "\n".join(
        f"- `{s['name']}` (module: {s['module']}, changed: {s['last_altered']})"
        for s in recent_sorted[:30]
    )
    return (
        f"**{len(recent_sorted)} SPs modified in the last {days} days:**\n\n{sp_list}\n\n"
        "Use `get_sp_definition('<sp_name>')` to review changes."
    )
