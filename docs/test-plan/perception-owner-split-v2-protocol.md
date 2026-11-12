# M10 explicit owner clock correction V2

Declared after the single V1 `owner5ms-01` attempt. That trial stopped after one
physical interval because `ObservedWorldClock` still required10ms. Its observer
failure, original1315-file freeze and native-fault-free termination remain FAIL;
this is a test integration defect, not evidence that the5ms plant failed admission.

TC-PER-100: explicitly bind the observed state clock to5ms for the declared owner
profile. Default10ms remains unchanged. Reject mixed/unknown periods and latch
frame/time mismatch; preserve actual source and receipt, gaps, duplicate handling,
100ms silence/expiry and all native deadlines. No adaptive clock or timestamp fixup.
Test the original first5ms callback path before launching.

TC-PER-101: one newly declared `owner5ms-02` run after corrected-source freeze and
independent archive tests. All V1 settings and acceptance limits are unchanged:
400 intervals,5ms/320substeps, HV30, no camera/no rendering/NullRHI/inline render,
three synthetic preparation calls and original state/IPC/authority checks. No
fence instrumentation or board optimization. This is the second overall attempt,
first with the explicit clock correction; never merge it into V1's denominator.

Preserve all original logs/receipts and this new freeze. If it fails, record the
failure and investigate from retained data; no retry under this protocol. A finite
owner-only PASS would permit work on the bounded scene snapshot prototype, not
claim2K rendering isolation or continuous driving acceptance.
