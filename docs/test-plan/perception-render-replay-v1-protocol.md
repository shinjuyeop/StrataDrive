# M10 separate renderer provenance diagnostic V1

Declared before any new CARLA launch. One renderer-only attempt `renderer-01`.
This is a prerequisite to simultaneous physics/rendering, not that experiment.

TC-PER-103: bounded actual-renderer-frame associations retain separate renderer
and authoritative frame/source identities, exact immutable scene bytes and
original acquisition/application/tick/callback times. A callback may precede its
tick RPC's return. No guessed frame, overwritten source or renewed scene age.
Eight pending mappings; unknown/evicted/duplicate callbacks do not resurrect data.
Original source, scene, callback and actual-state ages remain exclusive100ms.
Kinematics alone always remain unavailable for perception; there is no boolean
override for missing complete scene export and no same-world IPC conversion.

TC-PER-104: use the original owner5ms V2 receipts at indices0/199/399 without
changing their timestamps. Only one new CARLA renderer at2300/Epic/Town03_Opt,
camera2560×1536/FOV90/50ms and renderer step50ms. Apply original ego body poses to
a distinct source→clone mapping with clone physics disabled. Eight camera warmup
ticks plus four ticks per retained scene; all callbacks, including warmup and
unmapped images, retained losslessly with a32-packet memory bound. No inference,
native control connection, source-world writes or concurrent physical run.

Actual post-tick clone transform matrices must match the requested original pose
within1e-4. Callback frame/source must match actual returned renderer snapshots;
all three physical samples must have at least one associated actual image. Old
scene acquisition must remain expired despite a new callback. Image content is a
diagnostic only: original wheel animation, other dynamic actors and original
traffic-light/weather states were not captured in the old owner receipts. The
renderer uses explicitly recorded ClearNoon/frozen-red lights; this is not proof
of complete scene fidelity. It must never be admitted to the existing perception
or vehicle-control path.

Freeze all current source/import dependencies and original runtime/SDK identities,
reproduce focused tests from the archive, then launch once. Keep every failure;
no parameter retry or successful-sample selection. Preserve original server logs,
raw images, callback mappings and cleanup. SIGINT exit130, no forced stop, restore
settings byte-for-byte and verify original runtime binaries. Add all new images
to future-quality exclusions; do not read holdout. No20Hz or whole-system claim.

Full-scene authoritative acquisition/application and concurrent owner/render
stall/exit tests remain required after this diagnostic, regardless of outcome.
