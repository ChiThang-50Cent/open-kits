# ddgs-search

Hybrid web search helper that combines DDGS and SearXNG, exposed in two ways:

- as an OpenCode custom tool via `ddgs-search.ts`
- as a Claude Code MCP server via `server.py`

The shared search engine lives in `ddgs-search.py`. Runtime-specific paths belong in local host config, not in this repository.

## Requirements

- Python 3.10+
- `pip`
- Optional: Bun or a compatible OpenCode runtime for `ddgs-search.ts`

## Files

- `ddgs-search.py`: core hybrid DDGS + SearXNG search script
- `ddgs-search.ts`: OpenCode tool definition
- `server.py`: Claude Code MCP server wrapper
- `requirements.txt`: Python dependencies

## Human Manual

## OpenCode Global Install

OpenCode global custom tools live under `~/.config/opencode/tools/`.

Recommended layout:

```text
~/.config/opencode/tools/ddgs-search/
  ddgs-search.ts
  ddgs-search.py
  requirements.txt
```

### 1. Copy or clone this directory

Example target path:

```text
~/.config/opencode/tools/ddgs-search/
```

### 2. Install Python dependencies

```bash
python3 -m pip install -r ~/.config/opencode/tools/ddgs-search/requirements.txt
```

If you use a virtualenv, install into that environment instead.

### 3. Configure Python for the tool

Set `DDGS_PYTHON_PATH` in your global OpenCode config.

Example `~/.config/opencode/opencode.json`:

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
- or `python3` if dependencies are already installed globally

`ddgs-search.ts` reads:

- `DDGS_PYTHON_PATH`, then falls back to `python3`

### 4. Verify

OpenCode should discover the tool from `~/.config/opencode/tools/` automatically. Verify with `/tools`.

You can also verify the Python side directly:

```bash
python /absolute/path/to/ddgs-search.py --query "OpenCode" --max-results 3
```

## Claude Code Global Install

Claude Code global MCP config lives in `~/.claude.json`.

### 1. Keep this project in a stable path

Example:

```text
~/tools/ddgs-search/
```

or if this project stays inside a larger repo:

```text
~/tools/opencode-kits/ddgs-search/
```

### 2. Install Python dependencies

```bash
python3 -m pip install -r /absolute/path/to/ddgs-search/requirements.txt
```

### 3. Register the MCP server globally

Example `~/.claude.json`:

```json
{
  "mcpServers": {
    "ddgs-search": {
      "type": "stdio",
      "command": "/absolute/path/to/python",
      "args": ["/absolute/path/to/ddgs-search/server.py"]
    }
  }
}
```

If this project is inside `opencode-kits`, the `args` path will look like:

```text
/absolute/path/to/opencode-kits/ddgs-search/server.py
```

Claude Code starts `server.py` with that Python, and `server.py` reuses the same interpreter by default.

### 4. Optional overrides

Optional environment variables for `server.py`:

- `DDGS_SCRIPT_PATH`: override the path to `ddgs-search.py`
- `DDGS_MCP_TOOL_PYTHON`: override the Python used by `server.py` when it calls `ddgs-search.py`

Defaults:

- `server.py` uses `ddgs-search.py` in the same directory
- `server.py` uses its current Python interpreter unless overridden

## Project Install

Use project install only when you want the integration scoped to one repository.

- OpenCode project tools live under `.opencode/tools/`
- Claude Code project MCP config lives in `.mcp.json`

Example Claude Code project config:

```json
{
  "mcpServers": {
    "ddgs-search": {
      "type": "stdio",
      "command": "/absolute/path/to/python",
      "args": ["/absolute/path/to/repo/ddgs-search/server.py"]
    }
  }
}
```

## AI Agent Install

Before installing, ask the user which scope they want:

- `global` (recommended): install once for the whole machine
- `project`: install only for the current repository

If the user does not care, recommend `global`.

### For OpenCode agents

1. Ask whether the user wants `global` or `project` install. Recommend `global`.
2. For `global`, put the tool under `~/.config/opencode/tools/ddgs-search/`.
3. For `project`, put the tool under `.opencode/tools/ddgs-search/` in the target repo.
4. Install dependencies from that location's `requirements.txt`.
5. Set `DDGS_PYTHON_PATH` in the matching OpenCode config scope.
6. Verify OpenCode discovers the tool automatically.
7. Do not hardcode machine-local paths into source files.

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

1. Ask whether the user wants `global` or `project` install. Recommend `global`.
2. Keep the repo in a stable absolute path.
3. Install dependencies from that directory's `requirements.txt`.
4. For `global`, add the MCP server to `~/.claude.json`.
5. For `project`, add the MCP server to `.mcp.json`.
6. Pass the absolute path to `server.py` in `args`.
7. Do not hardcode machine-local paths into source files.

Suggested config snippet:

```json
{
  "mcpServers": {
    "ddgs-search": {
      "type": "stdio",
      "command": "/absolute/path/to/python",
      "args": ["/absolute/path/to/ddgs-search/server.py"]
    }
  }
}
```

## Notes

- OpenCode global custom tools are discovered from `~/.config/opencode/tools/`.
- Claude Code global MCP servers are configured in `~/.claude.json`.
- Keep machine-specific paths in local config, not in git.
- This repository can be published safely because runtime paths stay outside source control.
