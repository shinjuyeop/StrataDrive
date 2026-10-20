# M4 pending-command settlement evidence

Baseline:29b8221, clean worktree. Previous966-test/timing/native/SDK TSan evidence is
unchanged in [m4_contract_review](../m4_contract_review/README.md).
[ADR-0059](../../../adr/ADR-0059-pending-command-allocation-settlement.md) defines the
pending/expiry contract; [prospective protocol](../../m4_settlement_protocol.md)
fixes the40 diagnostic and48 timing runs before execution.

## Reproduction before correction

`build/m4-settlement/before`:29b8221 production + two new tests. Focused4 tests:
existing12ms/19.8ms reproducers PASS, new live-pending and pending-admission tests
FAIL (CTest exit8). Original request/response/physical/event CSVs retained.
After initial correction the exclusive19.8ms case protects at1025.4ms instead of
the premature1025.2ms. Both12ms still protects for previous applied command expiry.

The first new all-normal assertion used persistent Front0.2ms/Rear19.6ms delays
and failed at1555ms Central observation (local Rear expiry1551.000001ms/service1551.2ms).
That wrong normal-capacity assumption is retained in `after-initial/`.
The positive regression now explicitly injects only1000–1020ms; a separate
sustained-delay regression requires expiry protection. No runtime deadline changed.
A subsequent draft build's missing braces triggered `-Werror=dangling-else`; the
test braces were corrected, with the failed build retained separately.

Diagnostic runner before-fix bookkeeping tests:1/8 PASS,5 assertion failures and
2 errors. Failed/timeout/warning trials could exit0; launch/parse errors aborted
remaining collection. The corrected eight tests run the real Python runner
process with a mocked workload and preserve actual exit codes. They are not
native workload/performance results.

Execution results and current source identity are appended after their actual runs.
M4 NOT CLOSED, learner REVIEW PENDING, system/Target NOT RUN; no M5 adapter.
