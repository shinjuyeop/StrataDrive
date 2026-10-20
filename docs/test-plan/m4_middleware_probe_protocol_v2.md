# M4 middleware probe v2 — observable reliable backlog and reader rejection

Date: 2026-10-20. Freeze before new36-run cohort. All load, process, clocks,100+3 inputs,6 conditions×2 candidates×3 repeats, durations, capacities and freshness criteria follow [v1](m4_middleware_probe_protocol.md).

V1 source d7115ff was30 PASS/6 FAIL (DDS up-loss3 and overflow3); **preserve every original verdict**. Zenoh18/18, DDS12/18. These failures exposed two observation gaps, not evidence that no network fault/overflow occurred:

1. Reliable DDS retransmitted all103 echoes after Zone→Central loss. Counting final receive totals alone missed late echoes already beyond their original30ms expiry. V2 additionally counts **expired echo arrivals** in Central CSV. Up-loss/delay requires observed loss, extra rejection or more than the1 intentionally expired baseline echo. No deadline/source is changed; a late echo is never a vehicle ACK.
2. DDS write returned success even while reader history rejected samples. V2 enables/reads `DDS_SAMPLE_REJECTED_STATUS` and `DDS_SAMPLE_LOST_STATUS`; total channel failures include these counters plus explicit API failures. A rejection counter may count retransmission attempts, **not unique lost messages**. The overflow criterion still requires a nonzero queue/resource signal. Do not infer bounded application memory or successful delivery from write success.
3. Read back actual DDS writer/reader history/reliability/resource limits/max_blocking_time. Setup fails if requested RELIABLE/KEEP_ALL/8/1/8/block0 was not applied. Existing namespace/thread/affinity/load and CRC/byte-identity controls remain mandatory.

The initial cohort is not reclassified. V2 is a new commit, new source digest and separate36 results. No other build/verification during this cohort. Any further FAIL stays in its denominator; no retry-to-PASS. This remains a candidate API experiment, not normal ECU command/Actual transport or a remote recovery test.
