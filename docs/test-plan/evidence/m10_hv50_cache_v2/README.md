# Explicit HV50/cache V2 with direct stock startup map

V1 failed in empty preparation before native START. This fresh series selects Town03 through one temporary GameDefaultMap field and restores the original config inode. See [protocol](../../perception-hv50-cache-v2-protocol.md). Not yet live acceptance.

## Recorded outcome

Final record: [PASS_EVIDENCE_AND_RESTORATION_ONLY](final-validation.json). This retains the original physical verdict; it does not close M10.

- `normal-30s-01`: PASS finite diagnostic; [original disposition](normal-30s-01/disposition.json).
- `normal-300s-01`: FAIL / not accepted; [original disposition](normal-300s-01/disposition.json).

The 300s case retained all 60,000 physics receipts and 300,003 native calls. The
first fault at 60.086015970s was Rear CommandExpired, propagated to power/BMS/drive.
An exact diagnostic replay shows the replacement Rear message was delivered
145,770ns after the preceding command expired. Front ACK ordering and all original
expiries are retained; see [diagnostic and archived sources](rear-command-diagnostic.json).
GC took about 13–17ms across four cycles, with no observed owner major-fault
increase. Closed-shard hints retained all raw bytes. Stock-renderer scene age
was about 496ms median and 524ms p95; it is not adopted for the next candidate.

All six runtime files, the stock default-map config's original inode, 13,947
original assets and the 100% host ceiling were restored. The lease hit its 30-minute
time limit during post-run evidence work; measured execution and both server
shutdowns completed before restoration. See [restoration](restoration-confirmation.json)
and [asset/config restoration](cache-execution.json).
