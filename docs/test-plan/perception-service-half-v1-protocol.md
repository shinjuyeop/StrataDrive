# Native communication service cadence diagnostic

This prospective comparison follows the HV50/cache V2 failure. An exact replay of
the original 60,000 receipts and 300,003 native calls reproduced a Rear Command
Expired rejection at 60.086015970s. The valid replacement was sent after the Front
ACK, but the 1ms service cadence delivered it 145,770ns after the previous command
expired. Sequential acknowledgement, command validity, and original work identity
remain mandatory.

- Candidate: explicit `--native-service-us 500`, profiled 30s/300s endurance only.
  The default remains 1ms. Absolute wall slots skip missed calls; no catch-up or
  synthetic wall time. ECU release periods, 5ms physics, and the independent
  2ms/4ms watch stay unchanged. Actual requested and observed cadence is audited.
- Retain existing ADR-0066 `wall5-hv50-v1`: HV dependency 50ms, source/Actual and
  command limits unchanged. Keep closed-shard sync/cache release, the bounded NVMe
  asset placement, owner visual-tag omission and the previously declared GC profile.
- Use the original source editor renderer, `t.MaxFPS 60`, 2560x1536, D-FINE-M960,
  existing thresholds, renderer 20Hz target/camera 10Hz target. The stock renderer
  comparison had about 496ms median scene age and is not adopted for this trial.
- Same four owner/two image cores, dedicated native and observer cores, 70% bounded
  host lease. Empty owner/editor preparation at 100% may take up to 600s each;
  actual trial readiness remains 180s. Restore the original six runtime files and
  all temporarily moved asset inodes. No privileged scope expansion.
- Run 30s then 300s, once each; stop on the first original failure. Every raw frame,
  original receipt, audit failure and source is retained and independently verified.
  Frozen replay must exactly match original native rows and first fault.
- Prior development/profiling images, including HV50/cache V2, remain excluded
  from future quality evaluation. No holdout inspection or threshold adjustment.

Passing these finite diagnostics does not establish complete scene provenance,
native perception acceptance, independent held-out quality, or close M10.
