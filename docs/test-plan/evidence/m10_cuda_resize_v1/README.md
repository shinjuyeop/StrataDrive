# Exact CUDA resize comparison

**Both the 30 s and the 300 s concurrent Host diagnostics passed.** The archive
checker reproduced the physical verdict and original hashes for 283 and 2,773 camera
packets respectively. Eight supplemental audits reproduced in each case and the
six shared runtime files matched their original hashes. [Sequence disposition](sequence-disposition.json) · [5 min archive validation](normal-300s-01/archive-validation.json)

| 300 s with 2K camera | CPU resize | CUDA resize |
| --- | ---: | ---: |
| Scene to result, median | 93.97 ms | 76.42 ms |
| Scene to result, p95 | 104.12 ms | 84.15 ms |
| Results at or beyond 100 ms | 321 / 2,772 | 9 / 2,769 |
| Fraction of wall time with a potentially fresh result | 5.30% | 21.09% |
| Longest gap without a potentially fresh result | 2,037 ms | 633 ms |

Both runs used the same 100 ms exclusive deadline. GPU resize yielded 2,773 camera
packets and 2,769 completed results. In the GPU run, raw camera delivery averaged
9.24 Hz and preprocessing took 12.07 ms median. The 21.09% is an upper bound
before physical source time, actual state age and visual fidelity checks. Actual ECU
perception admissions were zero. The finite physical fixture spent most of its time
holding at rest. [GPU original timing](latency-300s.json) · [CPU original timing](../m10_service_half_v1/latency-300s-audited.json)

All 60,000 physical receipts and 599,962 native service calls matched the original
replay. Peak CPU temperature was 87 °C with no observed hardware throttle counter
increment. The original Intel P-state values were read back independently after the
lease log relay exited. Its final event was APPLIED, so the exact restoration instant is
unknown. All 13,947 original asset files were restored. [Replay](normal-300s-01/replay.json) · [CPU readback](host-restoration-readback.json) · [Asset restoration](cache-execution.json)

At the native observation points, 3,449 of 15,000 reads (22.99%) could have used a
completed result under the original time checks if transport were instantaneous.
Timing at these discrete reads and coverage over continuous wall time have different
denominators. The recorded native receiver accepted zero results. [Native observation replay](native-read-freshness-300s.json)

## Component evidence

The GPU executes the same two integer resize passes as the original CPU path.
Model weights, RGB bytes, tensor conversion and all deadlines remain unchanged.
Twelve original/synthetic inputs matched RGB and float32 tensors exactly.
CUDA memcheck reported zero errors and zero leaked bytes. At70% in an isolated
component comparison, median preprocessing fell from17.63ms to8.28ms and main
worker CPU time from15.18ms to5.59ms. These are not concurrent live results.

`component/` retains the prototype benchmark, exact release build hashes and
release memory-check results. The initial actual model preparation attempt
overlapped archive reads and failed its existing library-read deadline; that
failure is retained. A second preparation run completed both GPU paths but its smoke harness omitted
an empty inference list; that original harness failure is retained separately.
After fixing the harness, the third run passed actual owner-to-worker handoff,
all six preparation calls, library identity, the GPU lifetime audit and shutdown.
Settled owner calls were29.67/32.09ms and renderer calls30.66/33.36ms at100%. Release byte/memory checks ran at100%, not the70% live
performance condition.

Follow the [prospective protocol](../../perception-cuda-resize-v1-protocol.md).
No complete-scene or native perception acceptance is claimed here.
