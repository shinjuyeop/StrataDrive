# M4 remote-contract review and open-failure diagnostics

Fixed before the cohorts run (2026-10-20). Baseline4a399af; previous cohorts and
M4 NOT CLOSED remain. No M5 controller adapter. System32 requirements/29 TC,
Target and learner acceptance are unchanged.

1. Each of the three remote defects first gets a failing regression against its
   original implementation, then focused correction tests. Preserve original948
   test names/assertions. The correction boundary has963 tests (15 new).
2. Full normal and ASan/UBSan run in fresh directories. A failure is retained,
   diagnosed and any follow-up execution uses a separate path/source identity.
   Changed-boundary TSan covers remote/codec/AsyncOwner/AsyncZone tests, process-local
   `setarch x86_64 -R`; no system ASLR change or warning suppression.
3. Native CommandDelivery diagnostic adds opt-in, per-owner bounded trace storage
   (no shared logger/no hot allocation), capturing original source/inner expiry,
   first enqueue/envelope deadline, dispatch, Leaf receive/completion, Zone result
   enqueue and Central result arrival. Overflow invalidates trace coverage.
   Trace changes get logical and full regressions; instrumentation cost is explicit.
4. **20 normal +20 TSan independent processes**, paired alternating order, each the
   existing `M4AsyncWall.IndependentOwnersRunActualNormalPath` test:1.8s, inherited
   allowed CPU set, OTHER/0, no injected load, no execution guard enabled (same
   original test). First run onward `STRATADRIVE_M4_RESULTS` and transport trace ON.
   PASS requires original assertions, no sanitizer diagnostics and complete trace.
   No retries, dropped failures or pooled denominator with historical results.
   Source fingerprint/environment/settings/JUnit/physical/events/transport retained.
   Compare source→enqueue→receive→dispatch→completion→receipt, not just duration.
   This is diagnostic wall timing, not the 2ms/4ms guard acceptance cohort.
5. After source changes, run the existing **48-run** native protocol unchanged in
   a separate new directory using `check_m4_faults.py --run-timing`: normal/ASan,
   CPU0/1, OTHER/FIFO,7ms/10ms load,normal/Drive-stop/Monitor-overrun,3 repeats,
   2.54s and original guard/protection limits. Transport trace is OFF for this
   cohort; do not attribute prior603fe24/77d411c results to the new source.
   No builds or other tests while either timing cohort executes.
6. Middleware analysis starts from preserved SDK stacks and exact version source.
   Distinguish wrapper synchronization, SDK lifetime/reclamation and TSan visibility.
   Do not suppress/close a warning from lack of reproduction or a source hypothesis.
   No new SDK runtime cohort is required unless a distinct testable hypothesis and
   fixed protocol justify it; missing Rust/kernel permissions are recorded precisely.

Host IO/FIFO technical acceptance is a proposal only; unsupported timing, SDK and
native TSan conditions remain open until their explicit acceptance decisions.
