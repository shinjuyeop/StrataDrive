# Maintainer inquiry draft — NOT SENT

Subject: Cyclone DDS11.0.1: full reliable RHC delete wait and a Writer bitfield TSan report

We are qualifying Cyclone DDS for a Host vECU transport adapter. The adapter is
not connected to control; qualification remains blocked. We request a supported
shutdown procedure or a narrowly applicable upstream fix, plus triage of the
specific TSan paths below. We are not asking for an endorsement of the whole SDK.

## Version / reproducible inputs

- Cyclone DDS11.0.1, source e54e991; GCC/G++11.4.0, Ubuntu22.04.5,
  Linux6.8.0-138-generic, x86_64 i7-11700 (8 cores/16 SMT threads).
- Normal SDK Release; SDK built with official SANITIZER=thread in separate Debug
  install. Probe O1/g/frame-pointer/pthread, assertions on; linked dependencies
  instrumented in the TSan profile. TSAN_OPTIONS=halt_on_error=0:exitcode=66:history_size=7.
  No additional suppression, annotation, atomic replacement or SDK patch.
- Normal lib SHA256:94768951fb704e169dfd94322eeb11d0673ace099ba44696bc2f142b0617cd8f.
  TSan lib SHA256:96b8129df69635cc0aa0e28bf81fd6864f34d162d03407d66c52794b6a359305.
- Two processes in separate Linux netns on one Host, veth10.88.0.1/30 and
  10.88.0.2/30, UDP/domain37, multicast disabled, unicast peer discovery,
  ParticipantIndex=auto. Each process has one public writer and one reader,
  volatile RELIABLE/KEEP_ALL, resources8/1/8, max_blocking_time0. Fixed-size sample
  storage, application queue8, bounded take budget8. No borrowed loan left open.
- SDK callbacks only update diagnostic counters (and deliberately hold50ms in
  the separate callback-delete case). They do not delete/set their own listener.
  Callback context remains alive through participant deletion.

## A. Delete while reliable receive is full

Smallest currently evidenced behavior: Central writes60 samples at5ms; Zone takes
20, then stops taking, waits for its own reply writer ACKs up to100ms, and calls
dds_delete(participant). The peer continues writing until its60-sample limit.
The API wait is not a deliberately blocked callback. Both processes were on
CPU1/OTHER0; the older diagnostic had allocation unwind/finest trace/per-packet
flush. Normal/ASan/TSan raw restart each timed out in that original cohort.

A separate parent-GDB observation of the same normal binary showed:

```
main: dds_reader_close -> ddsrt_cond_wait
recv: ddsi_deliver_locally_allinsync -> remote_on_delivery_failure_fastpath -> dds_sleepfor
gc:   gcreq_queue_thread -> dds_sleepfor (awaiting awake-thread progress)
```

The original trace repeatedly redelivers sequence29 after consuming20 and filling
the8-sample RHC. ddsi_delete_reader unlinks the reader and queues GC; connection
removal/status callback is in gc_delete_reader. The retry loop appears to retain
an awake scope until the full RHC accepts data, while main no longer takes.
The source review and stacks are attached, not a claim that every interleaving
hangs. ACK wait's rc was not captured; GDB located the subsequent reader close.

Comparison: explicit sender quiescence while continuing takes allowed close.
Separating CPU1/2,20ms, minimal observation also closed, including a dedicated
case that stops takes at20, observes sample_rejected=1, deletes while the sender
is alive, and observes51 sends after the delete marker. These successes do not
resolve the original hang; multiple conditions changed. SIGKILL/timeout cleanup
has not been counted as successful DDS deletion.

Questions:

1. Is participant deletion expected to return while a remote reliable writer
   continues transmitting to a full reader that the application no longer drains?
2. Which supported API/configuration sequence interrupts this retry/GC dependency
   without requiring remote cooperation? Does it provide any bounded-return contract?
3. Is there an accepted patch/commit fixing this exact receive/full-RHC path in
   or after e54e991? We will compare it in an isolated build before adoption.

## B. Concrete Writer bitfield report

Raw: operating archive `cohort-v1/tsan-close-saturated/zone-42.stderr:146`, groupG08.
GC writes `ddsi_writer_clear_retransmitting` at endpoint.c:674 under the Writer
mutex; tev reads `test_suppress_heartbeat` at hbcontrol.c:599 **after** unlocking
that mutex at590. The report compares write2/read1 at0x7b580000197c.
endpoint.h:85–94 places these flags in consecutive bitfields. Disassembly of the
exact TSan library shows both access byte offset0x17c: the write is a load/AND0xf7/store,
the heartbeat path a load of that same byte. This is a built-in Writer allocated
by participant creation; our program never changes test_suppress_heartbeat.

4. Does this shared storage require a separate non-bitfield test flag or a
   lock-protected snapshot, even though the test flag remains false? Is there a
   supported minimal fix? We have not made either change without upstream guidance.
5. PR2162 is closed/unmerged and mentions related atomic/bitfield work. Is any
   accepted narrower change applicable to this exact Writer path?

## C. Remaining TSan paths / requested scope

64 warning occurrences across the preserved candidate runs reduce to32 pairs of
function stacks, not64 independent bugs. Publication bucket/GUID9 occurrences have
a concrete vendor atomic/TSan visibility gap; none is waived. Remaining55 include
bucket reclamation13, Writer14, WHC5, match-node6, mutex destroy3, participant1,
TKMAP5, proxy3, lease2, proxy mutex2, and the bitfield1 above. All raw FAILs remain.

6. For public write/take/discovery/teardown at this pin, can you confirm the
   specific awake-scope/reclamation contract for ACKNACK's deferred WHC list and
   match-node/Writer mutex lifetime, and TKMAP→serdata/lease references? Which of
   these reports needs a code fix versus a supported instrumentation explanation?

We know the general GC explanation in1417 and TSan discussion in1252/2039.
ASan-clean observations and broad GC suppressions are insufficient for our gate.

## Proposed attachments / replay (not newly run for this inquiry)

Repository base: StrataDrive658562e; complete reviewed artifacts:

- `docs/test-plan/evidence/m5_dds_qualification/raw.tar.gz`: exact v6 source snapshots,
  build commands/SDK hashes, `cohort-v6/*/restart`, `restart-gdb/zone-42.json`,
  `.trace`, `.command.json`, plan/result and GDB6s/outer32s cap.
- `docs/test-plan/evidence/m5_dds_operating_profile/raw.tar.gz`: v1 sources/commands,
  candidate runtime QoS/thread readback and all raw TSan logs; readiness-v2 kept separate.
- This directory's warnings.json, warning-review.md, shutdown-review.md and
  raw.tar.gz source-review/disassembly/identity records.

To replay only the old fault, rebuild the archived v6 probe using its recorded
build-commands in a separate checkout/install; do not substitute current sources.
After creating a fresh output directory, use the archived runner's single-case entry:

```bash
unshare -Urnm python3 <v6-checkout>/tests/integration/middleware/check_dds_lifecycle.py \
  --inside <fresh-output> <rebuilt-v6-normal>/lifecycle-probe restart
```

The outer controller must retain the original35s cap and all process/log outcomes.
Hold the repository build lock; no parallel builds/timing. The archive command
files specify absolute paths and environments that must be mapped to the new checkout.
For candidate TSan evidence, use the v1 snapshot with SD_CENTRAL_CPU=1,
SD_ZONE_CPU=2, SD_PERIOD_MS=20, SD_OBSERVER=minimal, SD_LIFETIME_TRACE=off and the
recorded sanitizer environment; scenario close-saturated. This is the smallest
existing scoped diagnostic, **not a newly minimized/validated standalone repro**.
The old occurrence rate is not a promise of deterministic reproduction.

After a supported candidate is identified, we propose one baseline/candidate run
per original raw-restart and Host saturated-close condition per applicable build,
fixed35s case cap, same QoS/queues/traffic, one SDK change at a time. No extra retry
without new evidence. Require actual API return, no unexplained warning, original
expiry/20ms/Epoch/token checks and closed control authority. That future comparison
is currently NOT RUN and needs its concrete candidate identity recorded first.
