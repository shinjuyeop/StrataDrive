# Unsent SDK support draft

No external issue or message has been sent.

Subject: vSomeIP3.7.6 TCP stop warning on cancelled wait and readiness target replacement

Version: COVESA release3.7.6, commit4187431d2815bd351845a09d01aa85b2a3163cab,
GCC11.4, Boost1.85.0, Ubuntu22.04.5/Linux6.8.0-138. Two separate netns/mount namespaces,
10.88.0.1↔10.88.0.2; independent routing managers, TCP, no events. JSON and exact build
flags are in the attached local evidence archive (would be reviewed before posting).

1. `tcp_server_endpoint_impl::connection::wait_until_sent` emits “Maximum wait time
   for send operation exceeded” on six observed branches with sending=false and
   error=operation_aborted(125), zero queue/train/dispatched train bytes and no reschedule.
   SDK stop and application dispatch join return; normal application results are complete.
   A logging-only separate library was used, default dependency unchanged. Is this
   cancellation/idle branch intended to have the same warning as a genuine send timeout?
   What public completion guarantees, if any, are provided by stop for pending TCP sends?
2. MT_REQUEST readiness on a surviving client's reconnecting TCP source port logs
   `set_client_target Target replaced`, even after giving the restarted server a new
   client ID. The inspected target key is service/method/client, excluding Session ID.
   Does the supported request/response contract require serializing all outstanding
   requests with that key across reconnect? Is there a supported release/patch that
   explicitly changes this behavior? Our adapter now uses two correlated one-way
   methods and does not invoke this response-target cache.

Minimal local references: runtime/someip-adapter-sdk-observed/{normal-1,close-full-1},
build/m5-someip-shutdown-observe/observe.patch and commands.json;
runtime/someip-adapter-tsan-final3/restart-live-1 retains the target replacement.
The latter completed actual Epoch2/8ACK/arm/control but correctly failed on the SDK error.
No ASan pass or chronology is used to dismiss a TSan race; no race report was observed
in these runs. Deliberate peer SIGKILL can additionally reset an outstanding original
RunLease send (101 bytes), accounted as injected loss rather than normal delivery.

Primary source references:

- [Official release3.7.6](https://github.com/COVESA/vsomeip/releases/tag/3.7.6)
- [Pinned TCP source](https://github.com/COVESA/vsomeip/blob/4187431d2815bd351845a09d01aa85b2a3163cab/implementation/endpoints/src/tcp_server_endpoint_impl.cpp)
- [Pinned server target source](https://github.com/COVESA/vsomeip/blob/4187431d2815bd351845a09d01aa85b2a3163cab/implementation/endpoints/src/server_endpoint_impl.cpp)

No request for broad SDK safety certification; questions concern these two observed
application paths and supported semantics only.
