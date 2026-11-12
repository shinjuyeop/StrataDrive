# Separate-world render provenance V1

Status: typed association and renderer-only diagnostic implemented; **complete
scene export and concurrent physical/rendering operation remain OPEN**. The
[corrected renderer trial](../test-plan/evidence/m10_render_replay_v2/README.md)
produced19 actual2K images,12 mapped images and a server shutdown failure. It is not
a successful whole-system run. The subsequent
[quiescent lifecycle trial](../test-plan/evidence/m10_render_shutdown_v2/README.md)
holds its final frame during storage and exits cleanly; the earlier intermittent
hang remains unexplained. No new result reaches the ECU perception receiver.

`render_provenance_v1.py` retains two independent identities: the authoritative
`SceneBinding`/frame/source and the renderer instance UUID/world/camera/frame/source.
World IDs can collide across processes, so numeric world ID inequality is not a
separation test. Neither clock is derived from the other.

Each `RenderAssociation` contains an immutable original `SceneSnapshot`, the actual
returned renderer frame/source, and application/tick wall brackets. SDK callbacks
may precede the tick RPC's return. A render worker records actual snapshot identity
before consuming an asynchronously recorded image; it never guesses a frame from
the requested tick. Eight pending associations are retained. Unknown, evicted or
duplicate callbacks produce no image association; identity/time corruption closes
the history. Shutdown discards outstanding associations.

`RenderedImage` retains native2560×1536 BGRA bytes and original callback receipt.
Original physical source, scene acquisition, callback receipt and observed-state
age have separate exclusive100ms checks. A new callback cannot refresh an old
scene. There is deliberately no conversion into the existing same-world
`NativeResult`/`Publication`/IPC type. Even a fresh kinematic image remains
`complete_scene_export_unavailable`; no caller boolean can override it.

The renderer adapter maps each authoritative actor ID to an explicit clone ID,
disables clone physics and applies original poses with no tick in the batch. It
converts PhysX/UE quaternion axes to CARLA pitch/yaw/roll and verifies actual
post-tick matrices. Clone creation uses a declared map spawn point before applying
the unmodified settled pose; creating directly at that pose failed CARLA's spawn
collision test. This preparation transform is never substituted for the source.

These poses describe the original body origin, not a demonstrated equivalence of
the original vehicle mesh/root/camera calibration. Kinematics alone omit wheel
animation and other scene state. The actual diagnostic uses explicit ClearNoon and
frozen-red traffic lights, not a reconstruction of their original states. The
frozen callback binds one camera; its numeric ID was not persisted in that trial
report, so independent evidence checks cannot recover that ID from raw pixels.
The new quiescent trial explicitly records renderer instance/world/camera and
calibration hash. This does not establish complete original scene fidelity.

The opt-in dedicated-renderer cleanup keeps the existing synchronous50ms settings
and verifies actual frame/source before and after packet storage. It does not
restore asynchronous WorldSettings or call ApplySettings to pause; that SDK API can
itself tick. Persistent INI restoration remains with the parent. Conditional thread
diagnosis begins only after10s of unsuccessful SIGINT shutdown, lasts at most8s,
and counts inside the original30s limit. No debugger runs during normal capture.

Before acceptance: capture complete authoritative same-frame scene/configuration
and visual state, verify body-to-actor/camera transforms and clone asset identity,
then define the typed result boundary. Preserve the earlier shutdown failure and
carry bounded diagnosis forward into a newly declared simultaneous
owner/render stall/exit case with all raw data. Existing native authority, HV30,
source/receipt deadlines and Jetson deployment scope remain unchanged.
