# M10 bounded endurance V2

The V1 protocol remains the acceptance policy. Its first attempt failed before
native INIT: the new310000ms request phase exceeded the original10000ms profile
validator. It executed zero physical intervals and retained six preparation
camera callbacks. V1 cases2/3 and300s were not run. This is a harness correction,
not a replacement of a failed physical measurement or a relaxed safety limit.

V2 declares a new three-case30s series. All three original paired audits and
exact native replays must pass before the conditional uninterrupted300s case.
The original V1 failure and all its raw exclusions precede V2.

The scenario ends its declared final hold phase at6500ms, within the original
request validation bound. The existing WallRig behavior extends this final
phase over its diagnostic service horizon. An explicit30/300s constructor option
now selects35000/305000ms for that horizon, matching the owner's duration+5s
recording watch. The previous10000/30000ms defaults remain unchanged. The long
option rejects absent CARLA model identity, any step other than5ms and any HV
dependency limit other than30ms. Native replay takes the same explicit option.

Leaf diagnostic event storage is preallocated to horizon_ms+12000 only for this
long harness; reaching it fails closed. Existing ECU releases, command expiry,
input freshness, physics authority and4ms execution checks remain unchanged.
Tests cover rejected scopes, original horizon behavior, final-hold acceptance,
long service horizon and persistent missing-input protection. Engine module,
model, renderer, raw recording and all V1 acceptance conditions are unchanged.
