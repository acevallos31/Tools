# Intent to tool routing

| User intent | MCP call |
|---|---|
| Current CPU/RAM/storage/uptime/firmware | `mikrotik_status(device, section="health")` |
| CPU over time | `mikrotik_status(device, section="health", duration=N, interval=1)` |
| CPU over time + graph | same call with `chart=true` |
| Interface state/counters | `mikrotik_status(device, section="interfaces", interface="etherX")` |
| Live RX/TX of interface over time | `mikrotik_status(device, section="interfaces", interface="etherX", duration=N, interval=1)` |
| Interface time series + graph | same call with `chart=true` |
| IPs/routes/gateway/connection tracking | `mikrotik_status(device, section="network")` |
| SSH session/reuse/fingerprint | `mikrotik_status(device, section="session")` |
| Who/what is generating traffic; hosts/protocols/ports/flows | `mikrotik_torch_flows(device, interface, duration)` |
| Complete inventory | `mikrotik_inventory(device)` |
| Explicit request for complete inventory AND live flows | `mikrotik_full(device, interface, duration)` |

## Negative routing rules

- CPU is never a Torch request.
- "30 seconds" by itself does not mean Torch; the measured subject decides the tool.
- Accumulated interface byte counters are not current bandwidth.
- Do not use `mikrotik_full` for a simple health or interface question.
- Do not call Terminal/subagents to reproduce functionality already exposed by MCP.
