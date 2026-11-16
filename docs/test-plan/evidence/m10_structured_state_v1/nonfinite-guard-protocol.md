# Post-failure nonfinite conversion guard, pre-START only

Code review after the failed30s sequence found that a direct JSON object could
carry NaN/Infinity where the old Serialize/Deserialize path rejects the number.
Add a recursive finite-number check to physics/work object handoff. Finite objects
remain direct; nonfinite objects take the exact original UE writer/parser path,
preserving its representation/rejection. Do not inject nonfinite vehicle state.

Extend the actual UE self-check with three nested nonfinite fixtures (+Inf,
-Inf,NaN), requiring both old parser and guarded path to reject, and require
finite fixture pointer identity. Retain4096 bit-exact finite values, actual static
physics, mutation and9 internal-envelope checks. Require the new fields in the
client before START. This guard is a post-live revision; preserve the original
build03,1428-file freeze and failed30s verdict unchanged. Build04 is a new isolated
candidate and is not a repeat of that live case.

After isolated compilation and Python tests, freeze the changed files, this
protocol/runner and build04 manifest with the parent source archive identity.
One owned null-RHI CARLA server uses the existing owner argv/CPU2,3,10,11, without
renderer, sensor, inference, native executable, shared bridge or native START.
Require CPU<=70C within180s, original runtime identities and free ports before
install. Readiness remains180s, client process60s, shutdown30s. Configure the
existing5ms synchronous physics settings, spawn one passive NoDrive vehicle,
perform one passive tick, bind and call structured_json_check once. Require all
checks and zero wall_frames/direct requests. No retry on error. Stop the owned
server and restore original module/INI in finally, verifying all original
runtime identities. Keep observed failure or success without claiming physical
stability, measured speedup or acceptance. No image/exclusion change.
