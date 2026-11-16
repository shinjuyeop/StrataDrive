# Post-failure native-only scheduler diagnostic

Declare after the original structured-state30s attempt failed and before this
separate diagnostic. The original30s sequence is closed: repeat30s and300s are
NOT_RUN_STOP_ON_FIRST_FAILURE. This diagnostic cannot replace those verdicts.

Run once, with no CARLA, renderer, inference or physical receipts. Use the same
frozen native executable,5ms model setting,2/4ms execution watch,30ms HV bound,
30s allocation profile, state-path records and original scenario. Launch on
Host V1 native CPUs1,9 with FIFO18. Send START then STOP at initial+1s. No
synthetic receipts or perception results are injected. Missing-input protection
is expected/recorded; only scheduler identity and actual watch rows are examined.
This is not a quiet real-time guarantee or a loaded comparison.

Before launch, require CPU<=70C within180s and record the executable/scenario/
script/profiler hashes. Keep the observer on CPUs0,8. Sample the owned process
threads, original clocks/thermal counters and read-only cooling-device state
every50ms; retain each observation's wall bracket and observer CPU cost. Record
actual /proc stat scheduling policy and RT priority as well as affinity. Infer
the monitor TID only from the sole non-main thread present before initial, when
the native source has not yet created its I/O thread; ambiguous identity stays
unknown. Do not change any host power, cooling, frequency, kernel, priority or
affinity setting outside the already declared owned process placement.

Initialization has a10s limit; stop and exit have5s limits. Preserve any error
and do not retry. Inspect all eligible monitor9 slots through the last native
service; list missing/late rows and wake-delay distribution. Keep full bounded
native traces, per-thread observations and original first fault. No new images,
no change to future exclusions, native perception acceptance remains zero.
