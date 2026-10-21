# Prospective DDS shutdown / warning follow-up — 2026-10-21

Base `658562e`; fetched origin/main identical, clean initial tree. Preserve all
earlier denominators, FAIL/OPEN/NOT RUN states; gate CLOSED, no control adapter.
No SDK replacement, suppression, authority/deadline change or administrator change.
Inherited Daybreak stop remains: stop any newly restricted request, preserve the
notice/time/context, and do not reroute it. External support is draft only.

## Fresh-checkout regression (fixed before execution)

One detached checkout of base without build/; one invocation of the existing29
Python tests (dds_lifecycle7 + middleware_probe22), 60s cap. Retain exit/log and
missing-directory failures. Apply only the preparation fix and strengthened
fixture to that checkout; one invocation of the same29 tests, same cap. Require
all original assertions and test names, compiler-shim exit7, complete NOT RUN
rows (24/38/6), and real timeout-child cleanup. This is Python bookkeeping with
mock SDK hashes/compiler failures, not a DDS runtime or sanitizer campaign.
Also run the same29 once in the working checkout after the fix, 60s cap.

## Existing evidence review

Read exact v6/GDB and operating-profile source/build/config/log identities.
Tabulate stopped take/full-RHC/peer writes/ACK wait/delete/waiting threads/results.
Classify all64 preserved TSan occurrences by both conflicting stacks, retaining
raw path, line, SHA and duplicate group. No warning is cleared by ASan success,
timestamp ordering or absence of a warning in another run. Only planned adapter
public write/take/discovery/lifecycle paths and existing diagnostics are in scope.

Consult pinned11.0.1/e54e991 source and official documentation/issues/releases.
A supported candidate needs a matching path and explicit expected effect before
any isolated build/runtime comparison. Record that candidate's single variable,
original vs Host conditions, repetitions, caps and unchanged oracles in an
addendum first. If none is established, do not repeat SDK runs: record NOT RUN
and prepare a maintainer inquiry with minimal reproduction and exact logs.
Forced cleanup is FAIL/administrative cleanup, never DDS API-close success.
Transport readiness is neither INIT/Release/arm nor runtime loss-deadline proof.
Performance and sanitizer verdicts stay separate. Original20ms envelope, inner
expiry, Epoch/token and protection assertions remain unchanged.
