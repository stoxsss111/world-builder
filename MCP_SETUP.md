# MCP Setup — Blender + fal.ai

Project-scoped MCP config lives in [`.mcp.json`](.mcp.json). Two servers:

- **`blender`** — official Blender Lab MCP, stdio.
- **`fal-ai`** — fal.ai hosted MCP, HTTP with bearer token from `${FAL_KEY}`.

When you first launch `claude` in this folder, it will prompt you to trust the project-scoped MCP — answer **yes**.

---

## 1. Blender MCP (official, by Blender Lab)

Two pieces: an **add-on inside Blender** + a **standalone MCP server** that Claude spawns.

### 1a. Install the Blender add-on

Blender 5.1+ required.

1. Open <https://www.blender.org/lab/mcp-server/>.
2. **Drag the install link into Blender twice** — first drop adds the Blender Lab repository, second drop installs the `MCP` add-on.
3. In Preferences → Add-ons confirm `MCP` v0.3.0 (or newer) is enabled.
4. In the add-on preferences enable **Auto Start**. Keep default host `localhost` / port `9876`. The status line at the bottom should read **Server is running**.

### 1b. Install the MCP server (the stdio bridge)

The PyPI package named `blender-mcp` is a different community project — don't use it. Install the official one from source:

```bash
# Clone the official repo (Blender Lab)
git clone https://projects.blender.org/lab/blender_mcp.git .tools/blender_mcp

# Install the MCP server as an isolated uv tool
python -m uv tool install ./.tools/blender_mcp/mcp --reinstall
```

`uv tool install` puts `blender-mcp.exe` (Windows) or `blender-mcp` (macOS/Linux) on your `PATH` once the uv tools bin directory is included. The shipped [`.mcp.json`](.mcp.json) invokes the executable by name (`blender-mcp`); if your shell can't find it, point the entry at the absolute path it landed at (`%APPDATA%\uv\tools\blender-mcp\Scripts\blender-mcp.exe` on Windows, `~/.local/share/uv/tools/blender-mcp/bin/blender-mcp` on macOS/Linux).

Prereq: `uv` (Astral). Install once: `pip install uv` (or follow <https://docs.astral.sh/uv/getting-started/installation/>).

### 1c. Verify

With Blender open (add-on running) and a fresh `claude` session started in this folder:

```bash
claude mcp list
# blender: …\blender-mcp.exe  - ✓ Connected
```

Available tools: `execute_blender_code`, `get_objects_summary`, `get_screenshot_of_window_as_image`, `render_viewport_to_path`, `get_python_api_docs`, etc.

---

## 2. fal.ai MCP

No local install — it's a hosted HTTP MCP at `https://mcp.fal.ai/mcp`. Just needs your fal key.

### 2a. Put the key in `.env`

`.env` is gitignored. Add:

```
FAL_KEY=<your-fal-key-here>
```

Get a key at <https://fal.ai/dashboard/keys>.

### 2b. Expose it to Claude's process env

Claude Code does **not** auto-load `.env`. Export the key for the shell that launches `claude`:

- **Windows (one-time, persistent):**
  ```
  setx FAL_KEY "<your-fal-key-here>"
  ```
  Close & reopen the terminal afterward.
- **macOS / Linux (per shell):** `export FAL_KEY=...` in your `~/.zshrc` / `~/.bashrc`.

### 2c. Verify

```bash
claude mcp list
# fal-ai: https://mcp.fal.ai/mcp (HTTP) - ✓ Connected
```

Tools: `mcp__fal-ai__run_model`, `mcp__fal-ai__submit_job`, `mcp__fal-ai__search_models`, `mcp__fal-ai__check_job`, etc.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `blender: ✗ Failed to connect` | Blender not running / add-on not enabled / port 9876 blocked. Check the add-on preferences panel reads "Server is running". |
| Tool calls hang | The add-on is connected to a *different* Claude session. Restart Blender, then restart `claude`. |
| `fal-ai: ✗ 401 / auth failed` | `FAL_KEY` not in process env. Run `echo %FAL_KEY%` (Windows) or `echo $FAL_KEY` to verify. |
| Tools missing after fresh connect | MCP tools register at session start. Quit `claude` fully and relaunch. |

## References

- Blender Lab MCP — <https://www.blender.org/lab/mcp-server/>
- Source repo — <https://projects.blender.org/lab/blender_mcp>
- Add-on extensions page — <https://extensions.blender.org/add-ons/mcp/>
- fal.ai MCP docs — <https://docs.fal.ai/integrations/mcp>
- Companion guide — <https://www.top3d.ai/learn/best-claude-blender-setup-2026>
- Claude Code MCP docs — <https://docs.claude.com/en/docs/claude-code/mcp>
