---
name: mikrotik-operator
description: Operate and troubleshoot MikroTik RouterOS devices through the local read-only MikroTik MCP server. Use for CPU, interfaces, routes, inventory, live traffic, Torch, timed monitoring and charts.
version: 0.8.0-dev
platforms: [windows]
metadata:
  hermes:
    tags: [mikrotik, routeros, networking, diagnostics, mcp]
    category: networking
---

# MikroTik Operator

Use the connected `mikrotik` MCP server as the source of truth. Do not replace an available MCP measurement with Terminal, a Python script, a subagent, remembered chat values, or invented samples.

## Procedure

1. Identify the device profile from the user's wording. If the target is unknown or ambiguous, call `mikrotik_devices`; do not guess an IP, hostname or profile name.
2. Map the intent using `references/tool-routing.md`.
3. Call the smallest MCP tool that directly satisfies the request.
4. Interpret the returned evidence using `references/interpretation.md`.
5. State uncertainty when the evidence does not prove a claim.

## Freshness rule

Words such as "ahora", "actual", "en este momento", "vuelve a revisar", "otra vez" or "consulta de nuevo" require a new MCP call. Never reuse an older CPU percentage or interface rate from conversation context as if it were current.

## Timed observation rule

If the user asks for CPU or interface traffic "durante N segundos/minutos", "monitorea", "muestrea", "promedio", "máximo", "mínimo", "tendencia" or a graph over time, use a timed `mikrotik_status` call. Do not simulate a time series by making unrelated point calls.

## Chart rule

When the user asks for a graph of timed CPU or interface traffic, set `chart=true` on `mikrotik_status`. The MCP produces the measurement and chart from the same readings. If the host does not render the image block, report the real statistics/readings and say the client did not render the chart; do not fabricate an ASCII graph or launch a plotting subagent.

## Safety

This MCP is intentionally read-only. Do not attempt configuration changes, reboot, upgrade or arbitrary RouterOS commands through Terminal as a workaround.

## Verification

A timed CPU result must contain `operation=cpu_sample`, `sample_count`, `statistics` and `readings`.
A timed interface result must contain `operation=interface_sample`, interface name, `sample_count`, RX/TX statistics and `readings`.
Torch results describe flows; they are not CPU measurements.
