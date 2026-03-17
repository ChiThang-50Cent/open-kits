# ddgs-search

Hybrid web search helper that combines DDGS and SearXNG, exposed in two ways:

- as an OpenCode custom tool via `ddgs-search.ts`
- as a Claude Code MCP server via `server.py`

The project keeps one shared Python search engine in `ddgs-search.py` and lets each host provide its own Python interpreter path.

Installation is path-based. Keep all runtime-specific paths in local host config, not in this repository.

## Requirements

- Python 3.10+
- `pip`
- Optional: Bun or a compatible OpenCode runtime for `ddgs-search.ts`

Install Python dependencies:

```bash
pip install -r requirements.txt
```

If you are using this directory from a larger repo, install with the full subdirectory path instead:

```bash
pip install -r /absolute/path/to/repo/ddgs-search/requirements.txt
```

## Files

- `ddgs-search.py`: core hybrid DDGS + SearXNG search script
- `ddgs-search.ts`: OpenCode tool wrapper
- `server.py`: Claude Code MCP server wrapper
- `requirements.txt`: Python dependencies

## Human Manual

## Path Layouts

This project can be used in either of these layouts.

### Standalone repo

If you clone this project as its own repo:

- repo root: `/absolute/path/to/ddgs-search`
- MCP server: `/absolute/path/to/ddgs-search/server.py`
- Python search script: `/absolute/path/to/ddgs-search/ddgs-search.py`
- requirements: `/absolute/path/to/ddgs-search/requirements.txt`

### Monorepo or subdirectory

If you clone a larger repo and this project lives under `ddgs-search/`:

- repo root: `/absolute/path/to/repo`
- MCP server: `/absolute/path/to/repo/ddgs-search/server.py`
- Python search script: `/absolute/path/to/repo/ddgs-search/ddgs-search.py`
- requirements: `/absolute/path/to/repo/ddgs-search/requirements.txt`

If you pulled `opencode-kits`, your real paths will look like:

- `/absolute/path/to/opencode-kits/ddgs-search/server.py`
- `/absolute/path/to/opencode-kits/ddgs-search/ddgs-search.py`
- `/absolute/path/to/opencode-kits/ddgs-search/requirements.txt`

### OpenCode setup

Set the Python interpreter in your OpenCode config with `env`.

Example `opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "env": {
    "DDGS_PYTHON_PATH": "/absolute/path/to/python"
  }
}
```

Recommended values for `DDGS_PYTHON_PATH`:

- a virtualenv Python such as `/absolute/path/to/venv/bin/python`
- or `python3` if `ddgs` is installed globally and already on `PATH`

Then register or load `ddgs-search.ts` from its actual location in the repo you cloned.

Examples:

- standalone repo: `/absolute/path/to/ddgs-search/ddgs-search.ts`
- monorepo: `/absolute/path/to/repo/ddgs-search/ddgs-search.ts`

The OpenCode tool wrapper in `ddgs-search.ts` reads:

- `DDGS_PYTHON_PATH`, then falls back to `python3`

### Claude Code MCP setup

Set the Python interpreter directly in `.mcp.json`. Claude Code uses that interpreter to start `server.py`, and `server.py` then reuses the same Python by default.

Example `.mcp.json`:

```json
{
  "mcpServers": {
    "ddgs-search": {
      "command": "/absolute/path/to/python",
      "args": ["/absolute/path/to/repo/ddgs-search/server.py"]
    }
  }
}
```

If this is a standalone repo, replace that path with:

```text
/absolute/path/to/ddgs-search/server.py
```

Optional environment variables for `server.py`:

- `DDGS_SCRIPT_PATH`: override the path to `ddgs-search.py`
- `DDGS_MCP_TOOL_PYTHON`: override the Python used by `server.py` when it calls `ddgs-search.py`

Defaults:

- `server.py` uses `ddgs-search.py` in the same directory
- `server.py` uses its current Python interpreter unless overridden

## AI Agent Install

Use this section when asking another coding agent to wire the tool into a machine or repository.

Follow this order, similar to plugin-style install docs:

1. Detect the repo root that was cloned or pulled.
2. Determine whether `ddgs-search` is the repo root or a subdirectory inside a larger repo.
3. Build absolute paths from that root.
4. Put those paths in host-specific config only.
5. Do not rewrite source files with machine-local paths.

### For OpenCode agents

1. Detect the absolute path to `ddgs-search/`.
2. Install dependencies from that directory's `requirements.txt` into a usable Python environment.
3. Set `DDGS_PYTHON_PATH` in OpenCode config.
4. Register or place `ddgs-search.ts` from that same directory where OpenCode loads custom tools.
5. Verify the tool can execute `ddgs-search.py` and return JSON.

Suggested config snippet:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "env": {
    "DDGS_PYTHON_PATH": "/absolute/path/to/python"
  }
}
```

### For Claude Code agents

1. Detect the absolute path to `ddgs-search/server.py` from the cloned repo root.
2. Install dependencies from that directory's `requirements.txt` into a usable Python environment.
3. Add an MCP server entry pointing to that Python.
4. Pass the absolute path to `server.py` in `args`.
5. Verify the MCP server exposes the `ddgs_search` tool and returns parsed JSON.

Suggested config snippet:

```json
{
  "mcpServers": {
    "ddgs-search": {
      "command": "/absolute/path/to/python",
      "args": ["/absolute/path/to/repo/ddgs-search/server.py"]
    }
  }
}
```

Verification examples for agents:

```bash
python /absolute/path/to/repo/ddgs-search/ddgs-search.py --query "OpenCode" --max-results 3
```

or for standalone layout:

```bash
python /absolute/path/to/ddgs-search/ddgs-search.py --query "Claude Code" --max-results 3
```

## Notes

- Do not hardcode machine-specific Python paths in source files.
- OpenCode and Claude Code each provide Python from their own config layer.
- This repository is safe to publish because runtime-specific paths stay in local config, not in git.
