# Exact CUDA resize comparison

Status: **component and both actual model preparation paths PASS; live comparison NOT RUN**.

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
The source freeze and actual evidence will be recorded before and after execution.
No complete-scene or native perception acceptance is claimed here.
