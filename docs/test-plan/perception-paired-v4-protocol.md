# M10 paired diagnostic V4: earlier fault observation window

Prospective protocol,2026-11-13. Adopts paired V3, including20Hz observation,
original5ms400 physical intervals, unchanged HV30/command/freshness guards and
all source/render/raw evidence requirements. The V5 normal audit is the passing
precondition; workload and normal execution code are unchanged.

V6's first conditional fault case retained400 passing physical intervals and
progress during the actual renderer stop, but the parent observed process death
26ms after the last physical acquisition. SIGKILL to observed death was412ms.
That whole case remains FAIL: progress after an exit request is not sufficient.

One new prospectively declared fault case changes injection thresholds:
SIGSTOP after180 intervals instead of220, actual Linux stopped-state observation,
SIGCONT at least250ms after the stop request, then SIGKILL after260 intervals
instead of320. The400-interval horizon and requirement for at least11 intervals
while actually stopped and at least11 after actual observed death remain. Death
must still be observed within1s; no timestamp renewal or deadline extension.

V6 also retained false actor-destroy returns after the server was already dead;
the original case would fail the cleanup criterion independently. The renderer
client now inherits the descriptor of the exact owned server process. In the
declared crash case only, actual pidfd exit observation permits skipping server
RPC cleanup of the camera and all three clones. Their IDs and skipped operations
are retained. Local inference/recorder cleanup must still succeed with no errors;
normal cleanup is unchanged. No generic ValueError or failed destroy is waived.
Tests require real process death and complete post-crash cleanup evidence.

This reserves about700ms of physical operation after the crash request rather
than400ms. It addresses the insufficient observation window, not a physical
failure or a renderer latency fix. Every prior failed case remains retained;
there is no retry to select a result. No new normal case is needed because the
changes affect conditional fault injection and already-dead server cleanup, not
the normal workload or native owner.
