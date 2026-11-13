# M10 paired diagnostic V3: bounded 20Hz scene observation

Prospective protocol, 2026-11-13. This adopts the complete paired V2 protocol
(`perception-paired-v2-protocol.md`), including its corrected pre-bind actor
placement, original physical guards and conditional renderer stop/crash test.

The single changed workload is cached receipt observation: the physical client
requests at most one scene observation per50ms instead of per20ms. SDK snapshot
callbacks still observe the original200Hz physical world, and the receipt still
joins the exact original physical frame/acquisition bracket. This does not change
the physical period, native commands, HV30ms protection,100ms freshness, rendering
resolution, renderer step, model or inference queue.20Hz is an observation cap,
not a required camera/inference throughput or an acceptance threshold.

The configured rate is recorded in the runner, client, source report and bound
catalog. Each query records its actual wall-clock begin/end and returned frame.
The auditor checks rate identity, ordered query brackets and receipt count.
These brackets include RPC queue waiting; they do not measure serialization alone.

V4's original normal failure (HV dependency30.334ms against30ms) and all its raw
images are retained. Reducing observation calls tests workload sensitivity; it
does not establish that RPC workload caused that failure. One prospective normal
attempt is made under this freeze. Only a passing normal attempt permits one
separately declared stop/crash case under this same implementation/rate. A pass
does not erase V4 or establish repeated-run/long-duration stability. No retry to
select a passing result is allowed. Every new case is retained and excluded from
future independent detector-quality evaluation.
