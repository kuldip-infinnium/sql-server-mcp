"""Analyze the database structure and build the schema cache."""
from .db import get_connection
from .cache import save_cache
import re


def _detect_module(sp_name: str) -> str:
    """Extract module prefix from SP name like usp_Translation_CRUDR → Translation."""
    match = re.match(r"^usp_([A-Za-z]+?)(?:_|$)", sp_name)
    return match.group(1) if match else "Other"


def analyze_database() -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    db_name = cursor.execute("SELECT DB_NAME()").fetchval()

    # --- Tables ---
    cursor.execute("""
        SELECT t.TABLE_SCHEMA, t.TABLE_NAME,
               COALESCE(p.row_count, 0) AS row_count_approx
        FROM INFORMATION_SCHEMA.TABLES t
        LEFT JOIN sys.tables st ON st.name = t.TABLE_NAME
        LEFT JOIN sys.dm_db_partition_stats p
               ON p.object_id = st.object_id AND p.index_id IN (0,1)
        WHERE t.TABLE_TYPE = 'BASE TABLE'
        ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME
    """)
    tables_raw = cursor.fetchall()

    # --- Columns ---
    cursor.execute("""
        SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE,
               IS_NULLABLE, COLUMNPROPERTY(OBJECT_ID(TABLE_SCHEMA+'.'+TABLE_NAME), COLUMN_NAME, 'IsIdentity') AS is_identity
        FROM INFORMATION_SCHEMA.COLUMNS
        ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION
    """)
    cols_by_table: dict[str, list] = {}
    for row in cursor.fetchall():
        key = f"{row[0]}.{row[1]}"
        cols_by_table.setdefault(key, []).append({
            "name": row[2],
            "type": row[3],
            "nullable": row[4] == "YES",
            "is_identity": bool(row[5]),
        })

    # --- Primary keys ---
    cursor.execute("""
        SELECT tc.TABLE_SCHEMA, tc.TABLE_NAME, kcu.COLUMN_NAME
        FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
        JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
          ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
         AND tc.TABLE_SCHEMA = kcu.TABLE_SCHEMA
        WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
    """)
    pks_by_table: dict[str, list] = {}
    for row in cursor.fetchall():
        key = f"{row[0]}.{row[1]}"
        pks_by_table.setdefault(key, []).append(row[2])

    # --- Foreign keys ---
    cursor.execute("""
        SELECT
            fk_schema.name  AS fk_schema,
            fk_tab.name     AS fk_table,
            fk_col.name     AS fk_column,
            pk_schema.name  AS ref_schema,
            pk_tab.name     AS ref_table,
            pk_col.name     AS ref_column
        FROM sys.foreign_key_columns fkc
        JOIN sys.tables  fk_tab    ON fk_tab.object_id    = fkc.parent_object_id
        JOIN sys.schemas fk_schema ON fk_schema.schema_id = fk_tab.schema_id
        JOIN sys.columns fk_col    ON fk_col.object_id    = fkc.parent_object_id
                                   AND fk_col.column_id   = fkc.parent_column_id
        JOIN sys.tables  pk_tab    ON pk_tab.object_id    = fkc.referenced_object_id
        JOIN sys.schemas pk_schema ON pk_schema.schema_id = pk_tab.schema_id
        JOIN sys.columns pk_col    ON pk_col.object_id    = fkc.referenced_object_id
                                   AND pk_col.column_id   = fkc.referenced_column_id
    """)
    fks_by_table: dict[str, list] = {}
    for row in cursor.fetchall():
        key = f"{row[0]}.{row[1]}"
        fks_by_table.setdefault(key, []).append({
            "column": row[2],
            "ref_schema": row[3],
            "ref_table": row[4],
            "ref_column": row[5],
        })

    # Build tables list
    tables = []
    for schema, name, row_count in tables_raw:
        key = f"{schema}.{name}"
        tables.append({
            "schema": schema,
            "name": name,
            "row_count_approx": int(row_count),
            "columns": cols_by_table.get(key, []),
            "primary_keys": pks_by_table.get(key, []),
            "foreign_keys": fks_by_table.get(key, []),
        })

    # --- Stored procedures ---
    cursor.execute("""
        SELECT ROUTINE_SCHEMA, ROUTINE_NAME, CREATED, LAST_ALTERED
        FROM INFORMATION_SCHEMA.ROUTINES
        WHERE ROUTINE_TYPE = 'PROCEDURE'
        ORDER BY ROUTINE_SCHEMA, ROUTINE_NAME
    """)
    stored_procedures = []
    modules: set[str] = set()
    for row in cursor.fetchall():
        module = _detect_module(row[1])
        modules.add(module)
        stored_procedures.append({
            "schema": row[0],
            "name": row[1],
            "created": str(row[2]),
            "last_altered": str(row[3]),
            "module": module,
        })

    schema_data = {
        "db_name": db_name,
        "table_count": len(tables),
        "sp_count": len(stored_procedures),
        "modules": sorted(modules),
        "tables": tables,
        "stored_procedures": stored_procedures,
    }

    save_cache(schema_data)
    return schema_data
