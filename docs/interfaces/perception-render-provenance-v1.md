# Separate-world render provenance V1

Status: typed association and renderer-only diagnostic implemented; **complete
scene export and concurrent physical/rendering operation remain OPEN**. The
[corrected renderer trial](../test-plan/evidence/m10_render_replay_v2/README.md)
produced19 actual2K images,12 mapped images and a server shutdown failure. It is not
a successful whole-system run. No new result reaches the ECU perception receiver.

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
frozen callback binds one camera; its numeric ID was not persisted in the trial
report, so independent evidence checks cannot recover that ID from raw pixels.

Before acceptance: capture complete authoritative same-frame scene/configuration
and visual state, verify body-to-actor/camera transforms and clone asset identity,
persist full renderer/camera session identity, then define the typed result
boundary. Resolve renderer shutdown and run a newly declared simultaneous
owner/render stall/exit case with all raw data. Existing native authority, HV30,
source/receipt deadlines and Jetson deployment scope remain unchanged.
