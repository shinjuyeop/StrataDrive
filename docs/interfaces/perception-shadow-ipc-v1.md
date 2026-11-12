# Native 2K same-host shadow IPC V1

`PerceptionIpcShadow` connects the existing2K receiver to the real
`m7_carla_wall_owner` process. It is opt-in and has no control/protection authority.
The original `Native2kControl::Required` logical SIL is separate; CARLA source time
must never be passed as the native wall coordinator's clock.

Python owns one prepared inference worker and a separate nominal50Hz publisher.
An inherited private `AF_UNIX/SOCK_SEQPACKET` pair is nonblocking on both sides.
The native owner drains at most4 messages per nominal20ms poll, each at most4984
bytes/100 detections. A full send records a drop; it never waits or renews a result.
A previously sent result becomes a poll. Unavailable/disconnect/expiry cannot
republish that old result. There is no reconnect or path-based endpoint discovery.

The C++ process receives trusted epoch42, actual CARLA world ID, and a same-host
monotonic clock identity through setup. Its accepted native INIT wall enable plus
first actual post-enable state establish the2K session. Source and wall timestamps
remain separate. Changed trusted INIT, state regression or clock regression closes
the receiver until a new process/session. Invalid identity, encoding, sequence or
transport age clears current data; later genuinely new valid data can recover in
shadow without granting vehicle permission.

All integers use explicit little-endian encoding; scores/boxes use IEEE binary64.
This is a finite private Host transport, not a remote Jetson wire/clock contract.

| Offset | Bytes | Field |
| --- | --- | --- |
| 0 | 8 | `S2KPIPC1` |
| 8 | 8 | version1, kind:0Unavailable/1Poll/2Result, uint32 each |
| 16 | 16 | uint64 sequence, uint32 epoch, zero reserved |
| 32 | 16 | source clock ID, wall clock ID, uint64 each |
| 48 | 32 | sender wall, actual state frame/source/receipt, uint64 each |
| 80 | 104 | Result only: schema/candidate, original frame/source/expiry/receipt/wall-expiry, camera/calibration/width/height/valid/count, model SHA256 |
| 184 | 48×count | uint32 class, zero reserved, binary64 score/x1/y1/x2/y2 |

The result portion uses the [typed native2K contract](perception-native-2k-control-v1.md).
Original source+100ms, callback-receipt+100ms and actual-state wall age<100ms remain
exclusive. Sender time is only a transport-age check; it cannot replace acquisition.
No-state is an explicit unavailable message with zero state fields, not a new clock.

The native trace pairs a copied receiver view with original P05Actual and records
IPC service duration. It performs no inference, camera RPC, file write or blocking
socket read inside the control loop. Existing vehicle watchdogs and gates still run.

[One live attempt](../test-plan/evidence/m10_live_shadow_v1/README.md) confirmed one
empty-detection2K result accepted in the actual process. The vehicle entered existing
protection before that inference and never armed; continuous driving remains OPEN.
The server still owns physical ticks through its existing authority/settlement
path. This trial is not the earlier free-running world latency benchmark.

The [startup follow-up](../test-plan/evidence/m10_startup_v1/README.md) corrected
the ECU release delay while retaining input protection. Its two world snapshots
were both received before native enable, so neither could bind the receiver;
0 fresh results were consumed. A late camera callback cannot create the missing
post-INIT world observation. Continuous delivery remains OPEN. The corrected
ownership-release-before-camera-destruction sequence completed in that live trial.
