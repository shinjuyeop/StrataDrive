# Dedicated SDK FIFO1 candidate

Base `3862ded`, prior finite soak v4:6/7. Loaded1 retained a real Rear command
expiry. Front token1924 took7.138231ms to return; its two SDK send-return to peer
callback intervals were3.717ms and3.054ms. Local owner processing was much shorter.
These intervals include transport and scheduling; they do not prove a particular
kernel lock or runnable wait. The candidate changes scheduling, not authority.

`front_run.py --sdk-fifo` opts into SCHED_FIFO priority1 for the three SDK processes
before init/start. SDK IO, dispatcher and sender inherit this policy on existing
dedicated CPUs4/5/6. Explicit owner placement remains Central1/FIFO11 and
Front2/Rear7/FIFO18. Plant3 and all auxiliary writers8 remain OTHER0. `chrt` setup
failure prevents ECU startup; original process snapshots independently check all
actual policies, priorities and CPUs. A missing declaration, wrong priority, or
auxiliary RT thread fails the audit. The original default remains OTHER0.

This is restricted to the noninstrumented finite Host terminal service profile
with separate owner/SDK and auxiliary physical cores. It is not a general SDK RT
bound or a Target guarantee. No system scheduler budget, power setting, SDK source,
queue capacity, control period, original timestamp, expiry, source-age limit,
Front-before-Rear ACK dependency or service deadline changes.

Before runtime, run affected Python regressions and reject invalid profiles.
Then run one fixed cohort: baseline500ms, quiet3 and loaded3 with each normal
Epoch2/3 held60s. Loaded demand remains70% on owner CPUs1/2/7. Retain every failure,
complete TCP capture and four original independent audits with mutations. Freeze
binary and changed runner/auditor/protocol hashes. Do not retry an unchanged
candidate until green. After the seven cases, run the existing split-v1 service
matrix18 (normal, four real service faults, delayed marker; three repetitions)
with this explicit policy. Every runtime precedes its offline audits; no build,
sanitizer, compression or other heavy work overlaps wall runs. Existing component
sanitizer evidence remains applicable because no C++ binary or SDK is changed.

Passing closes only this finite loaded Host profile. Record actual response tails
and all failures rather than infer a statistical latency bound from this sample.
