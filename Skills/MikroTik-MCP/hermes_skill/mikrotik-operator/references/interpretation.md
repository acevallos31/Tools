# Evidence interpretation rules

## CPU

A point `cpu_load_percent` is instantaneous. It can be described as "the current/instantaneous sample", not as sustained load or a trend.

A timed CPU result supports statements only about the returned observation window. Average/min/max/median are deterministic calculations over those readings.

Do not infer the cause of CPU load from traffic without additional evidence.

## Interfaces

Counters such as RX/TX bytes, packets and link-downs are cumulative. They do not prove current bandwidth or a current outage.

Timed interface sampling uses RouterOS `monitor-traffic ... once` repeatedly and returns current RX/TX bits-per-second for the observation window.

A link-down counter is historical. An enabled interface that is not running may simply be unplugged.

## Torch

Torch is a bounded flow snapshot. It supports statements about observed hosts, protocols, ports and rates in that capture only.

Do not claim:
- the connection is stable,
- there is no malicious traffic,
- a host is the cause of high CPU,
- the interface is the Internet/WAN path,

unless separate evidence proves the claim.

## Firmware

A RouterBOARD current/upgrade firmware difference is informational. Do not say an upgrade is mandatory or that the difference caused instability without release-note or operational evidence.

## Errors and missing evidence

If a tool errors or data is absent, say that it is unknown. Never replace missing evidence with a plausible value.
