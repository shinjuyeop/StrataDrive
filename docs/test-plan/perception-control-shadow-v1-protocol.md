# M10 native2K actual-owner shadow protocol V1

Declared before the first live attempt. This is development integration, not
quality acceptance, a holdout, normal driving acceptance, or runtime promotion.

- Existing D-FINE-M960 FP32 and native2560×1536 BGRA, FOV90, Epic postprocess;
  unchanged six class thresholds, both exclusive100ms deadlines and actual-state
  receipt100ms. Same prepared inference owner, three synthetic preparation calls.
- Town03_Opt spawn0, Lincoln MKZ2020; relative camera x1.4/z1.7. Pre-bind150
  passive settling ticks, no camera attached and no native INIT/control writes.
  Retain every subsequent camera packet, including cold/late/failed packets.
- Existing actual native WallRig and server-owned wall tick path, model10ms,
  HV dependency30ms, 320 solver substeps. No client ticks after bind. This is
  distinct from the earlier free-running async world camera benchmark: physical
  execution still follows the existing native authority/settlement gate.
- Inference/source observations/publisher run independently. Private inherited
  nonblocking AF_UNIX SOCK_SEQPACKET, max4984bytes,100 detections, max4 receives
  per nominal20ms native poll. One immutable current result. No new vehicle
  request, planner, protection authority or remote clock mapping.
- Parent passes trusted epoch42, actual CARLA world ID and random same-host wall
  domain ID. Native accepted INIT wall enable plus first actual post-enable
  state bind the receiver. Original image source/receipt/expiries never renewed.
- One fresh server, target200 physics intervals,18s client loop horizon,96 raw
  frame memory slots (overflow fails and spills originals),180s startup,
  900s total client/cleanup,30s server SIGINT shutdown. No hidden retries.
  Existing native watchdog, admission and authority limits remain unchanged.
- Preserve complete sent packets/dispositions, native receiver snapshots, original
  P05Actual, native wall watch, server events/solver receipts, model calls and raw
  BGRA hashes. All received RGB hashes enter the future quality exclusion set.
- Component acceptance: real Python/C++ process/socket interop, identity, malformed
  input, full queue, expiry, no resurrection, disconnect, bounded drain and tests.
- Live shadow delivery requires a real post-INIT2K result accepted by the actual
  native owner, original times verified against sent bytes/model call, and both
  deadlines/state freshness satisfied at the native read. Record availability
  denominator including unavailable reads; no20Hz requirement.
- Driving acceptance remains separate. Any original native/server protection,
  no physical progress, insufficient live image delivery, missing raw/trace or
  cleanup timeout remains FAIL/incomplete with original cause. Do not relax
  contracts, retime input or relabel synthetic component tests as live success.
- Freeze executable/import/build dependencies and runtime hashes before live.
  Restore existing module and GameUserSettings after the owned trial.

## Traceability

- TC-PER-088: typed bounded process transport, original clocks and fail-closed cases.
- TC-PER-089: actual native owner/CARLA one-attempt shadow delivery and original Actual;
  separate driving/lifecycle verdicts, all failed observations retained.
- TC-PER-090 (post-live addition): teardown after exclusive ownership close, parent
  removal and rejection cases; correction is unit-tested and not a new live result.
