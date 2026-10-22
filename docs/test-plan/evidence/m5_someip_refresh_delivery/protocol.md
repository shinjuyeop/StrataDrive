# Host command renewal: prospective protocol

Baseline b624243eaf6720f6ce455f6e0464c096e489c87c; HEAD/origin/main identical and clean at start (2026-10-22). Previous fifo-refresh artifacts and withdrawn candidates remain immutable.

Scope authorized by user: real eight-participant Host functional SIL Central↔Front SOME/IP, existing local Rear/Leaf/plant fixture. Host phase/renewal period changes are allowed, explicitly separate from legacy profile. No deadline/source rewriting, queue enlargement, native 4 ms or transport 20 ms relaxation. Rear implementation excluded. OTHER load timing diagnostic only; sanitizer wall time separate from memory/UB/race correctness.

## Development checks (before changes)

1. Add bounded permission-limit observation, identify the limiting original input in a deterministic real-owner logical network. Replay the observed small source/phase skew (69,603 ns support deficit) without inventing authority. Capture legacy normal failure and original Leaf expiry.
2. Implement an explicit Host renewal profile, preserving default legacy 20 ms contracts. Compare once per concrete candidate with the same deterministic acquisition/transport schedule. Required: next fresh command actually received by Steering, Brake and Drive before previous original expiry; all source/expiry values immutable; interrupted renewal still expires/protects.
3. Run affected coordinator/management/allocation/async owner contracts during development. Additional runs require a recorded code correction or new specific hypothesis. No repeated whole-suite development runs.

## Final frozen campaign

After focused checks, record source/binary hashes before running. No build or heavy search during wall timing.

- Normal FIFO, no load: normal ×2; existing OTHER load children on owner CPU1/2: normal ×2.
- Normal FIFO command-loss, owner-pause, central-stop, restart-live ×1 each, after existing real normal prerequisite.
- ASan/UBSan and TSan fixed-layout: normal + command-loss ×1 each; SDK instrumentation included. Full Normal and ASan unit/regression suite once on final common-code source.
- Original runner duration 2540 ms normal, supervisor 20 s; existing fault-case durations/timeout unchanged. Logical run 1800 ms, deterministic finite schedule, no retries.
- CPU/policy: Central1 FIFO11, Front2 FIFO18, physical3 FIFO19, monitors0 FIFO20; SDK/sender4/5 OTHER0, plant auxiliary6 OTHER0. Record actual affinity/policy/RT limits from runner. Native owner opportunities2ms / deadline4ms unchanged.

Success: real eight ACKs + RunLease + arm; real feedback/model response; no normal missing/expired commands, early protection or native timing misses; positive actual Leaf renewal margin across consecutive normal commands; expected fault protection by original authority bounds; orderly SDK stop/join and new Epoch rejoin. Normal availability and fault protection judged separately. Unexpected SDK/sanitizer errors, timeout, missing data or forced cleanup remain FAIL/raw exit1. Memory claims only for executed instrumented paths.

Full48 timing, all SDK combinations, extreme/compound faults and historical nonreproduced OPEN analysis NOT RUN. Existing acceptance denominators and OPEN records unchanged. Acceptance requires the above, not closure of unrelated historical OPENs.

## Candidate fixed before SDK execution

host10-v1: allocation/real VehicleRequest acquisition10ms (legacy20ms), VM10ms
phase+4ms unchanged, actual input acquisition/Leaf10/20ms unchanged. Permission
admission requires original expiry strictly after nominal release+18ms (10ms next
renewal +8ms phase/async handover reserve); source≥release and live independently
received matching grant retained. Legacy profile keeps its20ms support check.
No arbitrary maximum transport delay is guaranteed:20ms remains rejection envelope,
not the normal handover target. Queue sizes/inflight serialization unchanged.

Diagnostic logical control identified SteeringActual+30ms+1ns as the first minimum
(ties are not a unique causal attribution). A finite actual500us acquisition grid
with offset430,396ns, owner200us grid, and Front feedback visibility delayed6ms
from1s reproduces a169,603ns deficit,100us different from the historical69,603ns.
This is a sufficient controlled phase reproduction, not proof of historical6ms
network latency. Saved historical exact-value unit remains unchanged.
Pre-fix renewal assertion exit1: no replacement, all three command expiries at
2,010,430,397ns; local expiry2,010,600,000ns precedes Central protection. After
profile change, same schedule gives102 accepted commands per Leaf, all positive
renewal margins (minimum5,230,397ns across three Leafs), no protection. Interrupted
renewal still expires/protects. Focused logical19/19, affected contracts85/85.
Python bookkeeping initially19/20: lazy new oracle import escaped test's import
path context; move import to module load, then verify. Existing unclosed offline
CSV handles are closed; neither change affects control execution.
