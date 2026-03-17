#!/usr/bin/env python3
# pyright: reportMissingImports=false

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
DDGS_SCRIPT = str(Path(os.environ.get("DDGS_SCRIPT_PATH", BASE_DIR / "ddgs-search.py")))
DEFAULT_PYTHON = os.environ.get("DDGS_MCP_TOOL_PYTHON", sys.executable)
DEFAULT_TIMEOUT_SECONDS = 30


def build_ddgs_command(
    query: str,
    search_type: str = "text",
    region: str = "vn-vi",
    timelimit: str | None = None,
    max_results: int = 8,
    page: int = 1,
    timeout: int = 8,
    snippet_length: int = 500,
) -> list[str]:
    command = [
        DEFAULT_PYTHON,
        DDGS_SCRIPT,
        "--query",
        query,
        "--search-type",
        search_type,
        "--region",
        region,
        "--max-results",
        str(max_results),
        "--page",
        str(page),
        "--timeout",
        str(timeout),
        "--snippet-length",
        str(snippet_length),
    ]
    if timelimit:
        command.extend(["--timelimit", timelimit])
    return command


def run_ddgs_search(**kwargs: Any) -> dict[str, Any]:
    command = build_ddgs_command(**kwargs)
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=DEFAULT_TIMEOUT_SECONDS,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ddgs-search command failed")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("ddgs-search returned invalid JSON") from exc


def create_server():
    from fastmcp import FastMCP

    mcp = FastMCP("ddgs-search")

    @mcp.tool()
    def ddgs_search(
        query: str,
        search_type: str = "text",
        region: str = "vn-vi",
        timelimit: str | None = None,
        max_results: int = 8,
        page: int = 1,
        timeout: int = 8,
        snippet_length: int = 500,
    ) -> dict[str, Any]:
        """Search the web with the existing DDGS + SearXNG helper."""

        return run_ddgs_search(
            query=query,
            search_type=search_type,
            region=region,
            timelimit=timelimit,
            max_results=max_results,
            page=page,
            timeout=timeout,
            snippet_length=snippet_length,
        )

    return mcp


def main() -> None:
    create_server().run()


if __name__ == "__main__":
    main()
