# Isolated renderer memory feasibility

The visual-tags V2 trial failed at4.097s before GC. Around that fault the owner's
major-fault counter rose199→202; its first later GC took482.734ms and included10
additional major faults. The post-run host swap was almost full. These observations
identify paging/storage investigation as necessary, but do not identify the exact
faulted mappings or prove RAM exhaustion at the fault. The existing resource
sampler includes RSS and MemAvailable: its minimum was8,153,686,016bytes available
near the first fault. New samples add swap/PSI and process fault counters to that
existing sampler; no extra resource observer is needed.

Before changing the integrated runtime, compare the installed packaged CARLA0.9.16
renderer and the current editor renderer in isolation. Use the same three-actor
catalog, map/XODR, frozen weather/lights and2560x1536 RGB/FOV90/sensor0.1s settings.
Each runs on6–7,14–15 at the restored100% host cap. No native ECU or detector runs.
Measure /proc RSS/swap, system memory, PSI and vmstat, readiness and exact lifecycle.
Keep version and executable/module identities; SDK compatibility alone is not
whole-scene or pixel equivalence. Do not infer integrated memory from an empty
single-process measurement.

Each process has180s readiness,48 synchronous50ms ticks within a separate60s
capture limit, and30s shutdown. Retain every original callback losslessly and
exclude all new RGB hashes from future quality data. No automatic retry follows
failure. A normal0 or130 exit is recorded exactly for this isolated smoke, never
substituted into the original integrated exit130 requirement. Restore INI/runtime
files after the comparison. No source-asset modification or full engine rebuild.

This is a feasibility/memory diagnostic, not a new physics, throughput, model
quality, independent holdout or M10 acceptance test. Do not overlap archive I/O
with either launch. Review the evidence before adding a packaged-renderer path.

The first packaged attempt stopped before cameras at the map identity check.
One separate map-only query observed Town10HD_Opt: the shipping wrapper did not
apply the editor's positional map argument. Both normal exits were130 and both
produced zero images. The packaged and source Town03_Opt OpenDRIVE files are
byte-identical (SHA256abf177bcd9b66cfefb7ac4919f6456815f1384f4229f1343c8a6a90bbb7713c9).
For the next single camera smoke, explicitly override GameDefaultMap and
ServerDefaultMap on the shipping command line before launch. Keep the original
exact SDK map name/XODR and actor/environment checks; do not normalize a mismatch
away or change any assets. Preserve all earlier attempts and source versions.

That command-line INI override also left the shipping server on Town10HD_Opt;
the second attempt stopped with zero images and exit130. The next source uses
the standard SDK `load_world(Town03_Opt)` before actors/cameras, with the remaining
portion of the original180s startup budget. Record both initial and loaded map
identities and require the same exact name/XODR. No map alias or clock conversion
is accepted. This corrects explicit target-world setup; it is not a passed
camera comparison or an extension of the startup deadline.

SDK world loading then passed the exact map, environment and actor checks and
retained23 native2K callbacks. The synchronous stock server did not exit within
30s (the post-request debugger also timed out); retain this as a failed lifecycle.
The source CARLA game-thread loop polls TickCue while synchronous, without an
exit-request predicate. One subsequent smoke explicitly ends sensors/actor use,
then applies asynchronous settings immediately before SIGINT and records that
post-capture transition. No recording/storage work is inserted while unparked.
Keep shutdown30s; disable the optional intrusive debugger for this stock smoke.
This is a declared cleanup change, not a relabeling of the preceding failed exit.
