# Preserved middleware TSan stacks: source-level analysis

Scope: read-only analysis of the exact preserved11.0.1/1.10.1 warning cohorts.
No new warning suppression, production SDK patch, SDK runtime rerun or M5 adapter.
Original wrapper TSan4/4 FAIL and SDK-rebuilt DDS2/2 FAIL remain in
[prior evidence](../../m4_followup/README.md). URLs and SHA256 in [sources.json](sources.json).

## Cyclone DDS11.0.1

The SDK-rebuilt normal Zone warning pairs `ddsrt_chh_lookup` reading `bsary->size`
(hopscotch.c:414) with `gc_buckets_cb` freeing the old bucket array
(entity_index.c:220–232). Both access stacks belong to SDK receive/GC threads.
They do not identify the application's stack Packet or a wrapper queue buffer.
The C wrapper invokes write/take/status from one application thread and copies
fixed payloads; no wrapper-owned concurrent access is established by these stacks.
This does not prove all wrapper lifetime behavior safe.

GC gathers awake threads' vtime then waits for progress/asleep in
[ddsi_gc.c](https://github.com/eclipse-cyclonedds/cyclonedds/blob/11.0.1/src/core/ddsi/src/ddsi_gc.c)
(lines38–102, queue thread204–214). The reader's awake/asleep transitions use
custom fences and vtime updates in
[ddsi_thread.h](https://github.com/eclipse-cyclonedds/cyclonedds/blob/11.0.1/src/core/ddsi/include/dds/ddsi/ddsi_thread.h)
(lines190–229). Crucially,
[atomics/gcc.h](https://github.com/eclipse-cyclonedds/cyclonedds/blob/11.0.1/src/ddsrt/include/dds/ddsrt/atomics/gcc.h)
marks ld32/ld64/ldptr and st32/st64/stptr helpers `no_sanitize("thread")` and implements
them as volatile loads/stores. On x86_64, ldld/stst are empty and acquire/release
fences are compiler barriers. Hence the prior whole-SDK `-fsanitize=thread` rebuild
**still excludes those vendor helper accesses**; saying every synchronization edge
was instrumented would be inaccurate. The library's TSan imports alone cannot
prove coverage of these particular edges.

This establishes a concrete sanitizer visibility gap in the observed reclamation
protocol. It **does not establish** whether the protocol is correct for every
interleaving or whether this free/read is an actual lifetime defect. No valid
happens-before proof can be reconstructed solely from the stack. A supported
upstream TSan-aware atomic/reclamation configuration (or reviewed instrumented
variant with matching memory-order proof), plus a minimal concurrent index/GC
reproducer with original and instrumented SDK side by side, is still needed.
Merely replacing volatile operations with stronger atomics changes the algorithm
and would not justify closing the original warning. No such replacement was made.

The earlier uninstrumented-SDK UDP/WHC/mutex stacks likewise cross invisible SDK
internals; they are not evidence that a C wrapper mutex alone fixes the issue.
OPEN-M4-MWTSAN-01 remains OPEN;11.0.1 production acceptance remains PENDING.

## Zenoh-C1.10.1

The official release tag's Cargo.lock pins Zenoh commit
`1211779c3647f5a96713dade452c546a07823580`, Tokio1.53.1 and Mio1.2.3.
The saved binary's exact internal lockfile/build flags are not independently
attested by the release tag; source comparison is version-level, not a DWARF
address-to-line proof. The first saved warnings involve allocation followed by
`ListenersUnicastIP::add_listener` async-task writes and Tokio/Mio eventfd/waker
use. The pinned
[listener source](https://github.com/eclipse-zenoh/zenoh/blob/1211779c3647f5a96713dade452c546a07823580/io/zenoh-link-commons/src/listener.rs)
(lines93–117) moves a Send future into Acceptor.spawn and guards its listener map
with zwrite. The
[TCP source](https://github.com/eclipse-zenoh/zenoh/blob/1211779c3647f5a96713dade452c546a07823580/io/zenoh-links/zenoh-link-tcp/src/unicast.rs)
(lines306–337) moves the listener socket/token/manager into that task.

Our C callback copies sample bytes within the callback and protects every queue,
size/head/count/failure-counter access with the same pthread mutex. It never calls
ECU/controller code. The saved interceptor-only warnings are inside uninstrumented
Rust runtime/SDK scheduling; they do not establish a race on that copied C queue.
They also cannot prove Rust task handoff/lifetime correct. Rust std, Tokio/Mio and
Zenoh dependencies need a compatible instrumented build, debug symbols and toolchain
provenance to distinguish SDK misuse from missing synchronization visibility.
`cargo`/`rustc` are absent in this environment. Full Rust TSan and new SDK cohorts
are NOT RUN; original warnings remain unresolved, not labeled false positives.
