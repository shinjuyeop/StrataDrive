# M10 structured state V1: conversion candidate, early watchdog failure

Executed2026-11-16 under the [frozen protocol](../../perception-structured-state-v1-protocol.md).
The candidate removes three internal JSON serialization/parsing roundtrips:
physics snapshot, solver work and the trusted internally built admission request.
Original external RPC parsing, authentication, source/expiry, physical computation,
class layout and protection remain. The candidate is opt-in with
`--structured-state`; it has not earned normal-driving or endurance acceptance.

## Original results

| Check | Result |
| --- | --- |
| Isolated module compilation | PASS; candidate `d44efb7667021f2ce1854e530ba906036445aa37e0fece406e09912f853181a8` |
| Computation/layout equivalence | Original physics/work bodies byte-identical; original data/virtual/reflection layout retained |
| Before-START actual UE JSON checks |4096 finite double patterns bit-exact, actual physics snapshot, mutation checks,9 internal envelope cases and fallback checks PASS |
| Original30s attempt | **FAIL** after42 INIT receipts;0 normal receipts |
| First native fault | `wall execution deadline` at214.005921ms after initial |
| Native slots |1210 eligible;2 missing monitor9 slots,0 late completed slots |
| State-path integrity | PASS:246 native calls,42 receipts/HV derivations |
| Structured-state audit | FAIL: missing `final_server` after early client exit; incomplete6000-receipt coverage |
| Exact native replay | FAIL:33 differing protection rows, original source fields equal |
| Original joint / shadow | FAIL (`original ingress clock`) / integrity PASS, live delivery NOT_DEMONSTRATED |
| Declared moving-prefix comparison | NOT_COMPARABLE: tickets200–900 absent |
| Repeat30s /300s | NOT_RUN_STOP_ON_FIRST_FAILURE |
| Raw/archive | All6 actual BGRA/RGB images verified; frozen1428-file audit reproduces original FAIL |

The last original describe reports42 direct internal requests and0 text fallback.
This demonstrates that the candidate ran, not that its performance or complete
receipt integrity passed. The failure occurred before normal operation. Do not
compare this INIT prefix to the earlier V3 moving prefix or claim a percentage
speedup. The unchanged numerical bodies and bit-pattern checks establish the
conversion preconditions, not whole-system behavior over every future state.

Monitor9 wakes2.197ms and2.378ms after its requested releases, then the existing
2ms release-grid policy skips slots104 and107. Their original4ms deadlines
expire with no completion. In the+/-16ms first-fault window, the native main
loop's maximum observed wake delay is8.697µs and body117.963µs. The first fault's
HV dependency age is12.540ms, below30ms: this is a different observed failure
from state-path V3's HV timeout. Original replay has no external execution-watch
fault input, so it cannot reproduce these protection rows; its FAIL is retained.

The fast host observations show frequencies rising from roughly800MHz before
START toward2.87GHz maximum around+203ms, with68°C and no package/core0 thermal
counter increment in that local bracket. Preparation had reached97°C. The
samples do not establish the cause of monitor wake delays or CPU clock behavior.
The existing0.5s process profiler collected no sample inside the short physical
span; actual monitor policy during this failed live case is unknown. Main and
I/O metadata record FIFO18 and CPUs1,9. The observer now also records `/proc`
scheduling policy/RT priority for future cases without additional file reads.

There were6 raw frames and2 completed inferences (one103.271ms scene-to-result).
No usable steady-state camera/latency or normal CPU performance claim follows.
Native perception acceptance remains0. Renderer/owner exited in1.817/1.317s,
within their original limits, and original CARLA/DXC/INI identities were restored.

## Separate native-only observation

After closing the failed sequence, the separately [declared diagnostic](native-isolation-protocol.md)
ran the same native binary once for1s with no CARLA, images, physical receipts
or injected results. Monitor TID was unambiguously identified before I/O thread
creation. All samples show FIFO18, affinity1,9. Its500 eligible slots have0
missing/late completions; median/max wake delay15.163/817.095µs. There was no
native first fault. This confirms settings in that unloaded observation only;
it does not explain or invalidate the loaded failure.

The50ms observer collected40 samples, using0.758CPU seconds over2.038wall
seconds including startup. Its maximum sample took21.925ms. Reading all cooling
devices is too expensive to transplant into the live low-cost sampler unchanged.
Only fan cooling devices had nonzero states in these samples. Neither idle-inject
thread presence nor these later read-only samples prove thermal clamping during
the failed run. Host power/cooling/frequency settings were not modified.

## Verification and retained evidence

A later code review identified an exceptional-input difference: direct objects
could carry nonfinite numbers that the old writer/parser rejects. The post-live
build04 adds a recursive finite-number scan; exceptional objects use the exact
legacy parser, while finite objects stay direct. Its module is
`8bbe91b297e10869cc76079b84bebcd3428f08a617361d8f0313998b06e1e017`.
The separately [declared before-START check](nonfinite-guard-protocol.md) ran once
in a null-RHI owner with no native process, bridge, camera or control interval.
All existing checks plus nested+Inf/-Inf/NaN rejection and finite pointer identity
pass in actual UE. Both wall frames and direct requests remain0; shutdown1.067s
and original module/INI/runtime restoration pass. This validates the guard,
not full physical execution of build04. Build03's original failure remains.

`nonfinite-guard-01/changed-sources.tar.gz` retains the nine changed-source/build
inputs atop the original freeze. There is a recorded orchestration order
deviation: this snapshot preceded the final Python PASS log by5.405s; thermal
qualification followed it by0.610s and installation came afterward. Source files
did not change in that interval. The actual pre-START guard observations are
retained separately from protocol ordering; do not claim strict order conformance.

- Pre-live Python483, frozen focused67 and unchanged native boundary40 tests pass;
  the original30/300s allocation/start/stop preflight is retained. After adding
  process scheduling observations and the nonfinite guard, Python484 pass. The
  live source freeze remains unchanged; the six modified profiler/guard/check
  files have separately recorded post-live revisions.
- Initial isolated build01 failed because an added declaration shifted generated
  header line numbers; preserving those lines fixed it. Build02 compiled the
  preliminary candidate; build03 includes the final internal-envelope checks and
  is the only native-concurrent candidate. Build04's guard is checked only before
  START. Build failure logs remain local.
- [Watch window and self-check](normal-30s-01/watch-analysis.json),
  [state-path integrity](normal-30s-01/state-path.json),
  [original verdicts](normal-30s-01/disposition.json),
  [replay](normal-30s-01/replay.json), [archive check](normal-30s-01/archive-validation.json)
  and [native-only result](native-isolation-01/result.json) retain separate scopes.
  Post-run analysis does not replace frozen acceptance.
- `retained-metadata.tar.gz` preserves24 checked original metadata/trace files and
  all42 unchanged receipt rows. Native-only `records.tar.gz` is independently
  byte-checked with member hashes before removing expanded duplicates.
- All6 original images remain locally retained; future exclusions15205→15211.
  Raw transport94,382,080→42,629,366bytes passes whole-tar expansion identity.
  Checked extraction deletion saves55,159,305bytes; native-record compaction saves
  640,044bytes. Total reclaimed107,552,063bytes. Free space observed afterward:
  NVMe70.233GB, `/d`439.591GB. Raw/run archives stay ignored; Git alone cannot
  reproduce raw-image verification. See the [artifact policy](../../artifact-storage.md).

Next diagnose monitor scheduling under concurrent load with explicit thread
identity and bounded, measured observation cost. Preserve2/4ms and HV30ms;
neither enlarge deadlines nor promote this candidate based on the INIT prefix.
Only after that, declare a new finite moving comparison and endurance sequence.
Prior HV failures, cooling/startup behavior, complete visual state, native
perception, independent quality, each Jetson deployment and M10 remain OPEN.
