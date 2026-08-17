# Pogs Test Harness Integration

This custom app is validated against the `pogs-test-harness` skill. The runner uses `/openai/project/cua/.skills/pogs-test-harness/SKILL.md` by default and accepts `POGS_TEST_HARNESS_SKILL=/path/to/SKILL.md` for other environments.

The validation contract follows that skill's workflow: understand the code, cover happy/edge/error cases, execute the tests, report observed failures, and keep integration tests isolated from live Chromium policy activation.

## Gates

- Unit: policy merge preview contract
- Unit: overwrite vs recursive merge semantics
- Unit: staged revision backup
- Security/error: profile traversal rejection
- MCP: initialize
- MCP: tools/list
- MCP: unknown tool rejection
- MCP: origin rejection
- MCP: bearer-token rejection when configured
- Live integration: CUA Chromium CDP runtime status
- Integration: policy.merge.preview
- Integration: policy.merge and policy.current round-trip using an isolated temporary state root

Run all gates with:

```bash
./scripts/run_test_harness.sh
```
