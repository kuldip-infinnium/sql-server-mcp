"""Entry point: `sql-server-mcp` CLI."""
import sys


def main():
    args = sys.argv[1:]

    if args and args[0] == "setup":
        from .setup import run_setup
        run_setup()
        return

    # Server mode — credentials from env vars OR ~/.sql-server-mcp.json
    from .server import main as serve
    serve()


if __name__ == "__main__":
    main()
