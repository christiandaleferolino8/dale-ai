# CUA Policy Control — MCP + CLI Automation

A narrow control plane for the deployed CUA runtime. MCP and CLI now share one tool registry, so the same contracts are available to ChatGPT/custom MCP clients and shell automation without duplicating implementations.

## Architecture

```text
                 shared core.py tool registry
                    /                  \
             MCP /mcp                  CLI
               |                        |
        profile allowlist          tools / call
               |                   inspect / smoke
               +-----------+------------+
                           |
                  Chromium loopback CDP
                  policy_merge.py bridge
```

The implementation combines high-signal patterns from MCPorter, mcp2cli, XcodeBuildMCP, MCP Inspector, Playwriter and Docker MCP Gateway while keeping the original CUA safety boundary. Their source code is not vendored.

## Shared tools

- `cua.runtime_status` — read CDP/browser version.
- `cua.browser_pages` — list current pages without exposing WebSocket debugger URLs.
- `policy.merge.preview` — run deployed CUA `deep_merge` behavior in memory.
- `policy.merge` — atomically stage a merged policy under app-owned state and revision-back up the previous staged policy.
- `policy.current` — read staged policy.

Browser operations remain read-only. `policy.merge` does **not** write `/etc/chromium/policies`, modify authentication, restart Chromium, or change Supervisor.

## CLI

```bash
bash ./scripts/cua-policy-control tools
bash ./scripts/cua-policy-control tools --search policy
bash ./scripts/cua-policy-control call cua.runtime_status
bash ./scripts/cua-policy-control call policy.merge.preview --args merge.json
bash ./scripts/cua-policy-control inspect --live
bash ./scripts/cua-policy-control smoke
```

Arguments to `call --args` may be inline JSON, a JSON file path, or `-` for stdin.

### Profiles / tool allowlists

Profiles are app-owned allowlists inspired by gateway/profile architectures. They do not affect system Supervisor or Chromium configuration.

```bash
bash ./scripts/cua-policy-control profile list
bash ./scripts/cua-policy-control profile set readonly cua.runtime_status cua.browser_pages
bash ./scripts/cua-policy-control profile show readonly
```

Set `CUA_MCP_PROFILE=readonly` before starting the MCP server to expose only that profile's tools.

## MCP run

```bash
export CUA_MCP_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
uvicorn server:app --host 127.0.0.1 --port 8765
```

For a ChatGPT custom app, publish `/mcp` behind TLS/authentication or a supported secure tunnel. Do not expose local CDP directly.

## Test harness

The deployment is wired to `pogs-test-harness` and exercises policy semantics, security guards, shared-registry consistency, profile isolation, live CDP, CLI calls, MCP calls and smoke probes.

```bash
bash ./scripts/run_test_harness.sh
# or
npm test
```

Set `POGS_TEST_HARNESS_SKILL` when the skill is installed somewhere other than `/openai/project/cua/.skills/pogs-test-harness/SKILL.md`.
