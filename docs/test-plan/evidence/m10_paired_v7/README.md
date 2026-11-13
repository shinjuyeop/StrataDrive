# M10 paired V7: physical progress through observed renderer death

2026-11-13. One prospectively declared conditional fault case passes
`PASS_DIAGNOSTIC_CASE_ONLY`. V5 supplies the normal precondition. Compared with
failed V6, injection occurs earlier and dead-server cleanup uses the inherited
pidfd of the exact owned process. Original400 intervals/5ms, HV30, command
deadlines,20Hz observation and100ms freshness remain unchanged.

- SIGSTOP requested at interval181; actual stopped state observed. SIGCONT
  followed250.846ms after the request.51 physical intervals began while stopped.
- SIGKILL requested at interval260; the parent observed actual process death
 452.493ms later.49 physical intervals began after that observation.
- All400 original intervals completed:238 normal,0 protection/fault/late/missing
  intervals. Model2.0s took2.001255 wall seconds; maximum normal HV dependency
  age22.806ms.2005 native service rows and400 receipts replay exactly.
- 37 scenes exported,20 renderer ticks verified,26 real images retained,19 mapped
  images and19 model calls overlapping physics. Every call detected a person.
  Scene acquisition→result median92.285ms, p95321.472ms, maximum328.233ms.
  Stall-delayed data stays diagnostic; no acquisition timestamp is renewed.
- The expected post-crash SDK timeout is retained. Actual child pidfd death
  observation precedes skipping sensor/three-clone/world RPC cleanup. Their IDs
  and operations are recorded; local inference/recorder cleanup has0 errors.
  The intentional renderer exit-9 is distinct from forced graceful shutdown.
  Owner exit130 took1.016s, with original settings restored.

The1346-file prospective archive passes45 focused checks;458 regression tests
pass. Tests distinguish actual death from an exit request and require every
skipped actor and a post-crash exit observation. All26 BGRA images and19 numeric
outputs are lossless; future exclusion is9271. No holdout was accessed.

V4's HV30 failure and V6's insufficient death-observation window/cleanup failures
remain original failures. This short low-speed Host case does not establish
repeated-run or long-duration stability. Complete same-frame wheel/bone/material
state remains missing, every image is unavailable for control and native accepted
perception results are0. Required-mode live protection, independent model quality,
full M10 and Jetson Thor/Orin NX deployment are not established here.

`check-live.py` extracts original sources and all raw evidence, reruns the frozen
auditor and rejects12 mutations, including fabricated post-death progress,
stop-request-only evidence and incomplete/death-unproven server cleanup.
