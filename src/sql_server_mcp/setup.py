"""Interactive setup wizard — prompts for credentials, tests connection, registers MCP."""
import getpass
import json
import subprocess
import sys
from pathlib import Path


CONFIG_PATH = Path.home() / ".sql-server-mcp.json"


def _config_path() -> Path:
    return CONFIG_PATH


def load_saved_config() -> dict:
    """Load credentials from ~/.sql-server-mcp.json if it exists."""
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_config(config: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")


def test_connection(server: str, database: str, user: str, password: str) -> tuple[bool, str]:
    """Try to connect with the given credentials. Returns (success, message)."""
    try:
        import pyodbc
        preferred = [
            "ODBC Driver 17 for SQL Server",
            "ODBC Driver 18 for SQL Server",
            "SQL Server Native Client 11.0",
            "SQL Server",
        ]
        available = pyodbc.drivers()
        drivers = [d for d in preferred if d in available]
        if not drivers:
            drivers = [d for d in available if "SQL" in d]
        if not drivers:
            return False, "No SQL Server ODBC drivers found. Install from: https://aka.ms/odbc17"

        for driver in drivers:
            try:
                conn = pyodbc.connect(
                    f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"
                    f"UID={user};PWD={password};TrustServerCertificate=yes;",
                    timeout=10,
                )
                conn.close()
                return True, f"Connected using '{driver}'"
            except pyodbc.Error:
                continue
        return False, "Connection failed with all available drivers. Check credentials."
    except ImportError:
        return False, "pyodbc not installed. Run: pip install pyodbc"


def run_setup() -> None:
    print("\n  SQL Server MCP — Setup Wizard")
    print("  " + "─" * 35)

    # Show existing config as defaults
    existing = load_saved_config()

    def prompt(label: str, key: str, secret: bool = False) -> str:
        default = existing.get(key, "")
        hint = f" [{default}]" if default and not secret else ""
        if secret:
            val = getpass.getpass(f"  {label}{hint}: ")
        else:
            val = input(f"  {label}{hint}: ").strip()
        return val if val else default

    server   = prompt("DB Server  ", "server")
    database = prompt("DB Name    ", "database")
    user     = prompt("DB User    ", "user")
    password = prompt("DB Password", "password", secret=True)
    alias    = prompt("MCP alias  ", "alias") or "my-db"

    if not all([server, database, user, password]):
        print("\n  ✗ All fields are required.\n")
        sys.exit(1)

    # Test connection
    print("\n  Testing connection...", end=" ", flush=True)
    ok, msg = test_connection(server, database, user, password)
    if ok:
        print(f"✓ {msg}")
    else:
        print(f"✗ {msg}")
        retry = input("  Continue anyway? (y/N): ").strip().lower()
        if retry != "y":
            sys.exit(1)

    # Save config
    config = {"server": server, "database": database, "user": user, "password": password, "alias": alias}
    save_config(config)
    print(f"  Credentials saved to {CONFIG_PATH}")

    # Register with Claude Code
    print(f"\n  Registering MCP as '{alias}'...", end=" ", flush=True)
    exe = sys.executable.replace("python.exe", "sql-server-mcp.exe")
    # Use the actual entry point script path
    import shutil
    entry = shutil.which("sql-server-mcp") or exe

    cmd = [
        "claude", "mcp", "add", alias, entry,
        "--env", f"DB_SERVER={server}",
        "--env", f"DB_NAME={database}",
        "--env", f"DB_USER={user}",
        "--env", f"DB_PASSWORD={password}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print("✓ Done!")
        print(f"\n  ✓ Restart Claude Code and you're ready to use '{alias}'.\n")
    else:
        print("✗")
        print(f"  Could not auto-register: {result.stderr.strip()}")
        print(f"  Run manually:\n    claude mcp add {alias} {entry} --env DB_SERVER={server} --env DB_NAME={database} --env DB_USER={user} --env DB_PASSWORD=<your_password>\n")
