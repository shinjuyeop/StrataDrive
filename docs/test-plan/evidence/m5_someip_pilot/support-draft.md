# COVESA 문의 초안 — 미게시

Subject: vSomeIP3.7.6 TCP connection teardown warning when completed application responses precede stop

Environment: Linux6.8.0-138 x86_64, GCC11.4, Boost1.85,
vSomeIP3.7.6 commit4187431d2815bd351845a09d01aa85b2a3163cab.
Two independent routing managers, mount/network namespaces, veth10.88.0.1/2,
TCP30501, SD UDP30490, nPDU request/response debounce/retention0,
512-byte payload ceiling,8192-byte endpoint queue limits. Application callbacks
copy into a capacity8 mailbox; owner thread processes messages.

Minimal reproduction: run the `normal` case with the repository pilot; exchange
one readiness request/response, then eight20ms cycles (parent request/result,
command request/result, Actual query/result). After Central has consumed all
responses it calls release_service, clear_all_handler, stop and joins start.
Front then calls stop_offer_service, clear_all_handler, stop and joins start.
Some Front logs contain `Maximum wait time for send operation exceeded for tse`.
Application correlation/expiry checks passed; stop/join returned in under2ms in
these samples. Raw logs, packets, exact commands and hashes are in the evidence
archive (`normal-final/normal-1`, plus instrumented cohorts). No shutdown hang
was observed here; this is not a report about Cyclone DDS.

At the pinned source's
[wait_until_sent](https://github.com/COVESA/vsomeip/blob/4187431d2815bd351845a09d01aa85b2a3163cab/implementation/endpoints/src/tcp_server_endpoint_impl.cpp#L996),
the warning is in the else branch of `is_sending_ && _error`; the receive EOF/reset
path calls this with operation_aborted. This appears also reachable when no send
is in progress, rather than exclusively when a sent_timer expires.

Questions:

1. Is this message intended to imply a real timer timeout, or can it also describe
   the no-send-in-progress EOF/reset branch? Is a more precise upstream diagnostic planned?
2. Is the public stop_offer/release→clear handlers→stop→join order supported for
   this single-owner application, including a peer that continues sending?
3. What supported API/contract, if any, guarantees a bounded drain of pending
   responses before stopping? We do not infer application completion from send().

No runtime suppression, SDK patch or timing-budget extension is proposed. The
instrumented SDK/Boost/project tests emitted no TSan diagnostics after fixing
process address layout. The earlier busy-sender queue-limit error was fixed in
our diagnostic by bounding outstanding requests; it is not claimed as an SDK bug.
