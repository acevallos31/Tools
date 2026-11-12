# Professionalization Research - MikroTik MCP

This note records design patterns studied before the next implementation pass. It is intentionally architectural: ideas are adapted, not copied verbatim.

## Repositories reviewed

### jeff-nasseri/mikrotik-mcp

Useful patterns:

- MCP-specific context optimization: concise tool descriptions and tool annotations.
- Real RouterOS integration tests using an ephemeral QEMU-backed RouterOS Docker container.
- Multi-device inventory support.
- Dedicated scopes instead of arbitrary CLI exposure.
- Separate SSH client, connector, configuration, inventory and scope modules.

What we adopt:

- Keep tool descriptions short. Put procedure and routing knowledge in the Hermes skill.
- Add a RouterOS sandbox integration suite that is opt-in and read-only for this project.
- Keep MCP registration thin and move measurement/analysis into domain modules.

### AliKarami/MikroMCP

Useful patterns:

- Typed tool schemas with strict bounds.
- Every tool has explicit read/write/destructive/idempotent/open-world annotations.
- A companion agent skill maps user intent to the correct tool and documents pitfalls.
- The response contains both concise model-facing text and structured data.
- Connection pooling, host-key pinning, error taxonomy, audit logging and correlation IDs.
- Diagnostics such as Torch are explicitly non-retryable because repeating a timed capture changes the observation window.

What we adopt:

- Read-only ToolAnnotations on every public tool.
- Strict argument schemas and bounded durations.
- Hermes companion skill with an intent-to-tool decision table.
- JSONL audit trail with correlation ID, tool, target profile, duration, status and redacted parameters.
- Timed diagnostics are never silently retried.
- Optional SSH host-key fingerprint pinning while retaining a documented lab compatibility mode.

### grammy-jiang/RouterOS-MCP

Useful patterns:

- Layered architecture: MCP surface -> domain service -> RouterOS adapter.
- Public-surface smoke/e2e tests rather than only testing internal helpers.
- Clear error categories and remediation guidance.
- Separate observability, transport, security and domain modules.
- TDD and sandbox validation are treated as safety controls, not just developer convenience.

What we adopt:

- Public MCP contract tests.
- Deterministic error codes and safe suggested actions.
- Separate collectors/samplers from MCP presentation.
- Smoke tests remain network-free and fast; hardware/RouterOS tests are a separate marker.

### mikrotik-mcp/mikrotik-mcp

Useful patterns:

- Persistent SSH connection pool with idle/reconnect observability.
- Central choke point for tool-call observability.
- Dedicated observability UI and redaction.
- Rich result views are presentation layers over structured evidence; presentation does not replace the evidence.
- Explicit RouterOS skills/prompts for workflow knowledge.
- Strong rule: missing evidence remains unknown rather than being inferred.

What we adopt now:

- Tool-call audit stream first; a dashboard can be added later over the same event format.
- Results explicitly distinguish instantaneous samples, accumulated counters and timed observations.
- No claim of stability, anomaly, causation or internet/WAN role without direct evidence.

## Hermes Agent documentation findings

Hermes supports per-server MCP tool filtering with include/exclude and can disable resource/prompt wrappers. Skills use progressive disclosure and are the right location for procedures, tool-selection rules and known pitfalls.

Design consequence:

- The MCP server exposes a small exact execution surface.
- A Hermes skill teaches Qwen how to choose and interpret that surface.
- Tool descriptions remain concise to reduce context pressure on the local model.

## MCP Python SDK findings

The Python SDK generates JSON Schema from type hints. Literal values become enums, and Annotated/Field can express numeric bounds and descriptions. ToolAnnotations communicate read-only/idempotent/closed-world semantics to clients. Tool results may contain both text and structuredContent, and can also include ImageContent.

Design consequence:

- Validation belongs in the tool schema and backend, not only in prose.
- Model-facing text should be concise.
- Structured data remains the source of truth.
- Charts can be emitted as standard MCP image content while preserving the underlying series.

## RouterOS documentation findings

- /interface monitor-traffic supports once and returns current RX/TX bits-per-second.
- REST monitor operations also accept once.
- Torch is a flow diagnostic and should remain separate from CPU/interface-rate monitoring.
- Timed or interactive diagnostics must be bounded.

Design consequence:

Three distinct observations are exposed:

1. Point-in-time system/interface state.
2. Time-series sampling for CPU and interface RX/TX.
3. Torch flow inspection for hosts/protocols/ports.

Accumulated interface byte counters are never described as current bandwidth.

## Target architecture

User
  -> Hermes Agent
      -> MikroTik Operator Skill (procedure/routing/interpretation)
          -> MCP Server (typed, read-only tools)
              -> orchestrator
                  -> session manager
                  -> RouterOS SSH adapter
                  -> collectors/samplers
                  -> deterministic analyzers
                  -> chart renderer
                  -> audit logger
                      -> RouterOS

## Public tool surface

Keep the public namespace intentionally small:

- mikrotik_status
  - point state for health/interfaces/network/session
  - timed CPU sample when section=health and duration>0
  - timed interface-rate sample when section=interfaces, interface is supplied and duration>0
  - optional chart for timed samples
- mikrotik_inventory
  - complete inventory only
- mikrotik_torch_flows
  - network-flow inspection only
- mikrotik_full
  - retained for explicit full diagnostic calls, not the default workflow

Hermes should normally see the first three; mikrotik_full can be excluded in normal local-model use if tool routing remains noisy.

## Release policy

Development commits do not bump the server version. The branch remains on a single -dev version until a tested milestone is ready. Version changes happen at release boundaries, not per fix.
