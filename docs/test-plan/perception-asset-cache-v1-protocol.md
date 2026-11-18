# Observed asset storage on NVMe: one prospective300s attempt

The packaged-renderer V1 attempt failed before native START: the source owner did
not become ready within180s. At the post-request diagnostic its main thread was
in Linux disk sleep and libc read; VmSwap was0. The actual asset filesystem is
rotating Toshiba DT01ACA100 HDD `/d`; the root/tmp filesystem is NVMe. This
establishes file I/O involvement in that startup failure, not the mapping behind
V2's earlier live HV expiry. Both servers exited130; retain the failed verdict.

An isolated FileOpenLog preparation used the same owner module/map at100%, no
native START/camera/model, and became ready in49.337s. It recorded15,097 opens
(15,085 existing unique paths). Resolve actual relative paths against the engine
binary directory. The selected13,947 asset/cache files total7,852,108,357bytes.
This warmer single-process observation is not a paired70% timing pass.

Copy only observed uasset/umap/xodr and derived udd/ddc files to a private NVMe
directory. Check every copied byte identity and source inode/size/mtime. Preserve
the unchanged300s recorder ceiling57,227,083,776bytes plus4GiB free. Before engines
start, rename each original beside its own path and install an exact symlink to
its verified NVMe copy. Do not remove originals, edit assets or copy whole engines.
Keep a durable recovery plan and reject live engines, changed originals or
unrelated replacements. Test normal/idempotent restoration, interrupted rename,
changed cache, unsafe paths and storage exhaustion before real installation.

The source asset bytes must remain identical before/after the entire launcher.
UE may update its derived udd/ddc cache; retain those changes separately and
restore the original inode/data afterward. All observed immutable asset changes
fail the placement check. Restore every original even after a failed trial, and
retain NVMe copies for investigation. A failed restoration is not completion.

Keep the entire packaged-renderer V1 runtime, source module, native binary,
map/sensor/model, four-owner/two-image placement,70% bounded host lease,
physics5ms/native2/4ms/HV30ms, GC61.1s, preview/purge, source stamps and all original
audits unchanged. Keep its explicit pre-native code prefetch, stock SDK target-map
load and post-client synchronous-wait release. No viewport MaxFPS or editor idle
feature is claimed for stock. Startup180s/model10s/shutdown30s are not enlarged.

Run one normal300s attempt after fresh preparation. No unrelated build/archive
I/O overlaps either preparation or physical work. Do not repeat this combination
on failure. Reproduce original audits from sealed sources and retain all frames
and the full prior exclusion chain. Storage-placement PASS is separate from
physical PASS; both remain separate from complete-scene/native/quality/M10 gates.
