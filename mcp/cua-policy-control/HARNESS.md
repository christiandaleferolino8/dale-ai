# Pogs Test Harness Integration

This project is gated by the deployed `pogs-test-harness` skill. The runner treats test failures as deployment failures and performs both unit and live integration checks.

## Coverage

- `policy_bridge.py`: recursive merge contract, overwrite semantics, revision backup, traversal rejection.
- `profiles.py`: default tool set, safe profile names, unknown-tool rejection.
- MCP: initialize, tool discovery, unknown-tool rejection, Origin guard, Bearer guard, live CDP, policy preview/stage/current round-trip.
- CLI: shared tool discovery, dynamic tool calls, live inspect/smoke, profile allowlist round-trip.
- Final smoke: live CDP reachability plus page listing through the shared registry.

Run:

```bash
bash ./scripts/run_test_harness.sh
```

The policy tests use temporary state directories and never activate `/etc/chromium/policies`.
