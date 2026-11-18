# Native communication service at 500 microseconds

**30s PASS; 300s PASS, including original archive verification and eight frozen
supplemental audit reproductions. M10 remains OPEN.**

The500us service cadence preserves sequential Front ACK→Rear delivery, original
command expiry, ECU release periods and independent watch deadlines. HV50 remains
the explicitly selected ADR-0066 profile. Source editor rendering replaces the
unsuccessful stock-renderer comparison. See the unchanged
[prospective protocol](../../perception-service-half-v1-protocol.md).

The300s case retained60000 physical receipts:59838 normal,162 initialization,
zero protection and zero expired physics. All1500000 eligible watch slots had
zero missing/late slots. Original599963 native calls replayed exactly with no
first fault. Physical300s took300.000982565 wall seconds. Four GC cycles completed;
the previous post-GC Rear CommandExpired failure did not recur in this case.
Minimum command margin was210597ns. This finite mostly-stationary fixture does
not establish arbitrary routes, repeated long-term stability or Target timing.

All2776 raw images and original numeric outputs remain preserved. The2772
diagnostic results had scene-to-result median93.97ms/p95104.12ms;321 reached or
exceeded100ms. `latency-300s.json` records the measurements. Even ignoring the
additional source/state/fidelity gates, valid-result wall coverage is at most
5.30%;10Hz frame spacing and original100ms scene expiry leave gaps after processing.
The actual complete-scene/native admission remains unavailable.

The next explicit [CUDA resize comparison](../m10_cuda_resize_v1/README.md)
reduces preprocessing while preserving pixels and model inputs. Complete visual
state, typed native integration, fresh independent quality and availability
acceptance remain required before closing M10.
