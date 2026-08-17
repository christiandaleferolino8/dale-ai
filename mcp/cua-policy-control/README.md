# CUA Policy Control — ChatGPT Custom App / MCP Server

A narrow MCP app for the deployed CUA runtime. It exposes read-only Chromium/CDP inspection plus safe policy staging using the existing CUA `policy_merge.py` semantics.

## Tools

- `cua.runtime_status` — read CDP/browser version.
- `cua.browser_pages` — list current pages without exposing WebSocket debugger URLs.
- `policy.merge.preview` — run the deployed CUA `deep_merge` behavior in memory.
- `policy.merge` — atomically stage a merged policy in this app's state directory and revision-back up the previous staged policy.
- `policy.current` — read the staged policy.

`policy.merge` deliberately does **not** write `/etc/chromium/policies`, modify authentication, restart Chromium, or change Supervisor. Activation is kept outside the MCP write surface.

## Local run

```bash
cd cua-policy-control
export CUA_MCP_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
uvicorn server:app --host 127.0.0.1 --port 8765
```

Test:

```bash
curl -s http://127.0.0.1:8765/healthz
curl -s http://127.0.0.1:8765/mcp \
  -H "Authorization: Bearer $CUA_MCP_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"smoke","version":"1"}}}'
```

## ChatGPT custom-app connection

ChatGPT custom MCP apps require a **remote MCP endpoint**. Do not expose the local listener directly. Put `/mcp` behind TLS and authentication, or use Secure MCP Tunnel where available. Configure the resulting HTTPS endpoint in ChatGPT Developer Mode and choose the matching Bearer/OAuth authentication mechanism.

Recommended app name: **CUA Policy Control**.

MCP URL after remote publication: `https://YOUR_HOST/mcp`.

## Test-harness wiring

In the deployed CUA runtime, this app is validated against the `pogs-test-harness` skill. The harness runner auto-detects `/openai/project/cua/.skills/pogs-test-harness/SKILL.md` when present; for other environments set `POGS_TEST_HARNESS_SKILL` to the skill path.

Run the complete validation gate with:

```bash
./scripts/run_test_harness.sh
# or
npm test
```

The integration tests use a temporary policy state root and never activate `/etc/chromium/policies`.
