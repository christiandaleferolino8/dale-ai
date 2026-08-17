# MCP + CLI automation references

High-signal repositories used as architectural references for this project:

- `modelcontextprotocol/inspector` — official MCP testing/debugging surface with CLI/proxy architecture.
- `getsentry/XcodeBuildMCP` — one package exposing both MCP server mode and direct CLI mode, plus agent skills.
- `openclaw/mcporter` — MCP runtime + CLI/code-generation toolkit; can turn MCP servers into reusable CLIs.
- `remorses/playwriter` — browser automation exposed through both CLI and MCP with stateful sessions.
- `knowsuchagency/mcp2cli` — runtime translation of MCP/OpenAPI/GraphQL into CLI commands without code generation.
- `docker/mcp-gateway` — CLI-driven MCP gateway, discovery, isolation, auth and multi-server lifecycle management.

These are references only; this repository does not vendor their source.
