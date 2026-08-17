# MCP + CLI automation integration references

The project was refactored around patterns observed in these public projects. No reference implementation is vendored or copied wholesale.

- `openclaw/mcporter` — one MCP runtime usable from scripts/CLI plus dynamic tool discovery. Integrated as a shared registry and generic `call` command.
- `knowsuchagency/mcp2cli` — runtime CLI projection, searchable tool discovery and compact machine-oriented output. Integrated as `tools --search`, dynamic JSON arguments and `--compact` output.
- `getsentry/XcodeBuildMCP` — one package with MCP and direct CLI modes sharing underlying functionality. Integrated as `core.py` consumed by both `server.py` and `cli.py`.
- `modelcontextprotocol/inspector` — shared core plus automation-friendly inspection/smoke workflows. Integrated as `inspect --live`, `smoke`, and real transport tests.
- `remorses/playwriter` — reuse of an already-running browser instead of spawning a second browser. Integrated by attaching read-only helpers to the existing loopback CDP endpoint.
- `docker/mcp-gateway` — profiles and explicit tool allowlists. Integrated as app-owned profile storage and MCP tool filtering via `CUA_MCP_PROFILE`.

Safety deviations are intentional: arbitrary JavaScript execution, browser navigation, host command execution, secret management, OAuth brokerage, container lifecycle control and system Chromium policy activation are not exposed by this app.
