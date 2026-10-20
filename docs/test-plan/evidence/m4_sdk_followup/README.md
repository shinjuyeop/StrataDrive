# M4 native and SDK TSan follow-up

2026-10-20, Ubuntu22.04/kernel6.8.0-138-generic, original UID1000.
M4 **NOT CLOSED**. No production runtime, deadline, SDK algorithm, suppression,
default scheduler, kernel or M5 adapter changes.

## Results and denominators

| Experiment | Planned/executed | Actual result |
| --- | --- | --- |
| Native full trace, normal20 + TSan20 | 40/40 | 40 PASS,0 warnings, runner exit0 |
| DDS11.0.1 official `SANITIZER=thread`, normal/overflow twice | 4/4 | 4 FAIL;4,4,6,15 warnings; aggregate exit1 |
| DDS atomic helper visibility | 9/9 | vendor3/3 warnings(exit66), C11 control3/3 clean(exit0), deliberate race3/3 detected(exit66) |
| Zenoh source TCP, stable baseline and full Rust TSan, two cases twice | 8/8 | baseline4/4 and TSan4/4 PASS |
| Matched Zenoh nightly, same C/C++ binary/runtime/features, partial/full instrumentation | 8/8 | partial4 FAIL(29,21,31,20 warnings), full4 PASS(0 warnings); aggregate exit1 |
| Clang14 + Rust LLVM23 runtime positive/negative controls | 6/6 | clean3/3 exit0, deliberate race3/3 detected/exit66 |

All failures are retained. Positive-control race detections are diagnostic
observations, not middleware PASS. These are concurrency/functional experiments,
**not performance acceptance**. A Python unittest run (~1s) overlapped the matched
SDK comparison; it must not be used as a quiet timing cohort. Native40 ran after
builds/SDK experiments, holding `build/.m4-exclusive.lock`.

[Metadata](metadata.json), [native results](native40/results.json),
[per-run native latency CSV](native40/latency.csv),
[DDS results](dds-official/results.json),
[matched Zenoh results](zenoh-comparison/results.json),
[instrumentation imports](instrumentation.json).
Full commands, original logs/CSV/JSON, exact build scripts and failure logs:
`sdk-raw.tar.gz`; native logs/transactions/physical/event/execution CSVs:
`native40-raw.tar.gz`. [SHA256 manifest](SHA256SUMS.json).
No toolchain or compiled SDK binary is checked into the repository.

## Native: no new causal conclusion

```bash
python3 tests/integration/runtime/check_m4_delivery_trace.py \
  build/m4-native-diagnostic-NEW
```

Actual cohort: `build/m4-sdk-followup/native40`, source `05e088b`, fingerprint and
environment in [metadata](native40/metadata.json). Existing test
`M4AsyncWall.IndependentOwnersRunActualNormalPath`,1.8s, OTHER/unpinned,
guards OFF/full transport trace ON, process-local `setarch -R`,20 runs per profile,
unchanged30s per-process diagnostic timeout. Maximum Central enqueue→result
normal0.442538ms / TSan0.427215ms; no submit rejection or first fault.

The `d7115ff` archived failure had first fault915.290114ms and protection
selection915.819030ms. Its original log lacks the request/token transport chain.
The separately saved diagnostic trace was a later PASS, not the failed run.
Neither the current40 PASS nor the independently corrected pending-allocation
contract establishes that old failure's cause. **OPEN-M4-TSAN-01 remains OPEN**.
Original973-per-build regression and48-run timing are historical results of
`97afb35`; neither was rerun or relabeled for this diagnostic-only change.

## DDS: supported build still leaves invisible synchronization

The exact11.0.1 CMake source supports `-DSANITIZER=thread`, which adds compiler
and linker instrumentation. The fresh official-option build reproduces
hopscotch/entity-index/GC free-read warnings as well as receive/mutex lifetime
stacks. [Actual commands](dds-official/plan.json) and compiler invocations/cache
are in the raw archive. The previous manual-flags build and failures remain intact.

`tests/integration/middleware/dds_atomic_visibility.c` isolates a single payload
handoff using the exact installed vendor helpers, with C11 and deliberate-race
controls. Three fixed repetitions per mode show TSan cannot observe that vendor
handoff: the payload read/write is warned, while C11 release/acquire is clean.
Assembly/logs and [plan](visibility/plan.json) are retained. The vendor header uses
`no_sanitize("thread")` volatile loads/stores and x86 compiler fences.

This demonstrates the visibility gap without patching the SDK. It **does not
prove** the complete entity-index GC/vtime protocol, all interleavings, language
memory model, or object lifetime correct. The C11 control is a different
diagnostic implementation, not a proposed stronger-atomic production fix.
The vendor's supported CMake switch does not introduce a separate TSan-aware
helper implementation in11.0.1. A reviewed reclamation/order argument or an
upstream supported equivalent is still needed. **OPEN-M4-MWTSAN-01 remains OPEN**.

## Zenoh: dependencies obtained and complete Rust instrumentation exercised

The official1.10.1 tag specifies Rust1.97.1. Both that toolchain and
nightly-2026-10-20 + rust-src are installed **only** under
`build/m4-sdk-followup/toolchain/{cargo,rustup}`; shell profiles/system packages
were not changed. Installer checksum, source archive checksum, commands and
results are in [Rust inputs](rust-inputs.json), [Rust results](rust-results.json)
and [SDK source](zenoh-source.json). Cargo uses `--locked`; the Zenoh revision
is1211779c, Tokio1.53.1, Mio1.2.3. Features are explicitly TCP-only for this
diagnostic, not all features of the previous standalone release binary.

The first TSan build failed(exit101). Its nested opaque-type generator inherited
`-Zsanitizer=thread` but did not receive `-Zbuild-std`, causing a libc/std sanitizer
ABI mismatch; the outer generator then reported missing generic signatures.
`zenoh-tsan-before/opaque-generator.stderr` in the archive preserves the inner
cause. The supported `CARGO_COMMAND` override now propagates `-Zbuild-std` to the
nested Cargo invocation. No `unsafe-allow-abi-mismatch`, warning suppression,
SDK source patch or atomic replacement was used. The resulting build succeeds;
std/Tokio/Zenoh/Mio archives have35/22/21/18 distinct TSan imports respectively,
with their Cargo fingerprints and SHA256 retained.

GCC11's old libtsan lacks the new Rust library's `__tsan_memcpy/memmove/memset`.
The diagnostic therefore uses one static LLVM23.1.4 runtime shipped by that
Rust nightly, Clang14 C/C++ instrumentation, `-fno-sanitize-link-runtime`, and
Rust `-Zexternal-clangrt`. Loader records confirm there is no second libtsan.
Six positive/negative controls verify observable detection on that combination.
This is an explicitly recorded interop experiment, not a blanket compiler/ABI
support qualification. A direct LLVM23.1.4 release API lookup returned404;
no global compiler installation was attempted.

The matched comparison rebuilds the uninstrumented Rust SDK with the **same**
nightly as the instrumented SDK, uses the same probe binary/runtime and TCP
features, and verifies identical generated opaque-layout hashes. Partial
instrumentation reports Tokio task publication/Zenoh transport writes across
invisible handoffs; full instrumentation produces zero warnings in all4 runs.
This is concrete evidence that partial instrumentation creates warnings in this
reproducer. It does not authenticate the old standalone binary's build provenance
or prove every old stack false. Some runtime frames used unsupported DWARF in
system addr2line; Rust source frames were present, and llvm-symbolizer14 resolves
the saved transport/task offsets. Original warnings remain retained.

Supported Rust method:
[Rust sanitizer documentation](https://doc.rust-lang.org/unstable-book/compiler-flags/sanitizer.html),
[rustup installation](https://rust-lang.github.io/rustup/installation/index.html),
[Zenoh toolchain](https://github.com/eclipse-zenoh/zenoh-c/blob/1.10.1/rust-toolchain.toml),
[DDS sanitizer option](https://github.com/eclipse-cyclonedds/cyclonedds/blob/11.0.1/CMakeLists.txt).

## Reproduction and remaining scope

Extract the archives into a **new** directory and inspect their `*-plan.json`,
`commands.json` and exact `*.py` build/run scripts before execution.
Those scripts record this workspace's absolute paths; select a new
`build/m4-sdk-followup` root in a separate checkout, or change that output root
consistently. Existing fixed cohort directories must not be overwritten.
Prerequisites are the pinned DDS install/probe build from the
[prior SDK protocol](../../m4_middleware_probe_protocol_v2.md).

For an existing built SDK/probe, each preserved `command.json` is directly
replayable after replacing only its output directory. The full Rust build uses
the archived pinned toolchains, `--locked --no-default-features --features
transport_tcp --target x86_64-unknown-linux-gnu`, and TSan adds
`RUSTFLAGS='-Zsanitizer=thread -Zexternal-clangrt -Cdebuginfo=2'` /
`-Zbuild-std` / the saved `CARGO_COMMAND` helper. Compilation and timing
collection must hold the common workspace lock and run sequentially.

Still pending: privileged fixed kernel cohort; old native failure's actual
failed transaction; DDS GC correctness; qualification of the pinned fully
instrumented Zenoh configuration/default-feature scope and original warning
provenance. Target/system/learner review remain NOT RUN/REVIEW PENDING.
