"""CLI entry point for movietime-mcp server."""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="movietime-mcp",
        description="MCP server that fetches movie showtimes from Fandango by location.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose/debug logging.",
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Print server info, then exit.",
    )
    args = parser.parse_args()

    if args.info:
        import json

        info = {
            "name": "movietime-mcp",
            "version": "0.1.0",
            "description": (
                "MCP server — fetch movie showtimes from Fandango "
                "by ZIP code, city/state, or theater name."
            ),
            "tools": [
                "get_showtimes",
                "get_theater_showtimes",
                "get_movie_details",
            ],
        }
        print(json.dumps(info, indent=2))
        sys.exit(0)

    from movietime_mcp.server import run

    run(verbose=args.verbose)


if __name__ == "__main__":
    main()
