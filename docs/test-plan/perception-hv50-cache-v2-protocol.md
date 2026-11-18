# Direct shipping startup map with the declared HV50/cache candidate

Retain every policy and audit in [V1](perception-hv50-cache-v1-protocol.md).
V1 never reached native START: empty owner readiness69.742s, stock initial
readiness118.941s, then SDK target-map loading exceeded the combined180s budget.
Both servers exited130 and the six shared runtime files were restored. No power
lease was applied. This is a preparation failure, not an HV50 result.

UE4.26 GameInstance.cpp explicitly ignores command-line map override in a
Shipping client unless compiled with UE_ALLOW_MAP_OVERRIDE_IN_SHIPPING. The
installed DefaultEngine.ini has GameDefaultMap=Town10HD_Opt. Change exactly that
one field to the already declared Town03_Opt for preparation and finite trials;
the same map/XODR identity is required. No asset or rendering setting changes.
Keep the original config inode beside its path, pin both config hashes, reject
unknown replacements, and restore the original after both servers stop. Unit
test restoration, the interrupted rename gap and preservation of unexpected edits.

Before the integrated attempt, an isolated stock camera smoke must observe
Town03 as its initial map and exit normally. In the actual runner and audit,
require initial_map==Town03 as well as the existing target-map/XODR/empty-world
checks. Do not silently fall back to two-map startup for this candidate.
Record this config in the source freeze as an external runtime input while
installed; restore before launching the wrapper, which installs it before
preparation and restores it in finally after the finite sequence.

Prospectively run30s then300s, stop on first failure, unchanged180s/10s/30s
readiness/model/shutdown bounds. V1 generated no new frames, so chain the complete
asset-cache V1 exclusion set. Actual images stay diagnostic and excluded from
future quality holdout. A successful run does not close the remaining M10 gates.
