# M10 state-path V2: explicit empty-renderer asset preparation

V1 ends with its original FAIL: renderer readiness exceeded180s while loading
and rebuilding skeletal meshes, and shutdown needed a forced stop at30s. No
physical interval or camera was generated. V1's second case is NOT_RUN. Preserve
that result and the earlier300s HV failure; neither is replaced by V2.

New condition: run one separate, declared asset-preparation server before the
measured sequence. Use the exact V1 renderer command and candidate CARLA/DXC
identities, no native owner, no actors/cameras/inference and no control admission.
Allow at most600s for this preparation only; once ready verify the empty world,
park it and apply the unchanged30s shutdown policy. Preserve its whole log,
readiness history and exit. Do not resave assets, delete caches or change host
power/clock/permissions. Engine-generated cache writes are normal preparation.
Restore the original module/DXC/INI afterward. If preparation fails, do not run
the measured sequence. This is a warm-cache diagnostic condition, not cold-start
acceptance or a change to the normal180s readiness bound.

After preparation, freeze source and runtime again and declare two30s cases with
exact V1 instrumentation/settings. The second is conditional on first physical,
shadow, exact replay and state-path integrity success. Stop on first failure;
no300s in V2. All original control limits, physical/camera/model rates, CPU
placement, storage/temperature preflight and full frame retention are unchanged.
No builds or compression during live. Restore originals after each case.

The only postprocessing correction canonicalizes a missing-file error's run-root
path so that an extraction path does not appear to change an original failure.
Do not change failure types/messages otherwise. Freeze and test this correction.
Chain exclusions from V1 (still14633). Full raw archive checks and lossless
compaction stay mandatory; Git stores review evidence, not generated raw/run
archives. Finite success does not close the earlier cold-start/HV failures,
native perception, full scene quality, Jetson deployment or M10.
