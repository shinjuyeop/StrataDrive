# Three-process Host SOME/IP Rear adapter

Work in progress; no new adoption verdict yet. Baseline `da5a669` Host FIFO
Central↔Front acceptance remains valid. See [prospective protocol](protocol.md)
and [three-ECU ownership/wire contract](../../../icd/someip_rear_adapter.md).

Development normal trial1/1 passed with actual8 ACKs,194 accepted commands per
Steering/Brake/Drive, original-expiry minimum margins13.511/13.508/12.842ms,
no native deadline miss, real NormalStop/HV-off and all SDK stop/join returns.
This development trial is not the final fixed campaign. Changed contract tests12/12
and Python bookkeeping23/23 passed. Initial test build failed on a dangling-else
warning in a new gtest assertion; braces corrected it. The immediately following
9-test stale-binary run is excluded, not counted as final source verification.

Final evidence and scoped verdict will be appended after the declared campaign.
