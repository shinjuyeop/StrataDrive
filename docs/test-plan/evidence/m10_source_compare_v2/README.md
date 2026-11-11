# 2K/4K source comparison — measured improvement, 20Hz still open

At unchanged D-FINE-M960 FP32, Epic/FOV90/postprocessing and5:3 aspect ratio,
2560×1536 improved the two finite camera observations to16.88/17.62Hz from the
new matched3840×2304 baseline of14.56Hz. It did not reach20Hz or real-time1×.
Default runtime, controller, ROS and Jetson deployment remain unchanged.

| Same V2 module, normal bytes copy | 4K baseline | 2K first | 2K second |
| --- | ---: | ---: | ---: |
| Received RGB / model calls | 100 /100 | 100 /100 | 100 /100 |
| Camera Hz, wall | 14.559 | 16.885 | 17.619 |
| Observed world Hz | 72.604 | 84.308 | 87.906 |
| Simulation / wall time | 0.726 | 0.843 | 0.879 |
| Receipt→backend mean ms | 62.378 | 50.232 | 48.718 |
| Capture→backend mean ms | 135.489 | 97.376 | 93.563 |
| Capture→backend P95 ms | 293.186 | 104.921 | 96.621 |
| Capture→backend max ms | 347.251 | 193.004 | 101.671 |
| Published / uniquely consumed | 92 /61 | 100 /99 | 100 /99 |
| Capture→first consumption mean ms | 130.938 | 106.526 | 103.568 |
| Sampled fresh reads, active interval | 18.92% | 44.93% | 47.18% |

Every model call, including cold/late results and timing tails, stays in the
capture→backend statistics. Consumption statistics are explicitly conditional on
consumption, not an alternative all-frame latency claim.100ms source age and100ms
offer-receipt wall age are unchanged exclusive deadlines; neither is identical to
capture→backend wall time. A mean below100ms does not imply every frame or the
consumer is below100ms. Unavailable reads still need the existing protective
integration; sampled fractions do not measure exact continuous availability.

Each live window is500..504 source frames (about5 simulation seconds), followed by
300ms stopped-camera observation. These short runs provide a directional comparison,
not long-term throughput/tail qualification. The physics step remains10ms and the
sensor schedule frame%5. The world is asynchronous; client tick count is0 and only
actual on_tick states advance the observed clock. The real-time1× target is not
replaced by deliberate slow simulation.20Hz remains the engineering Reference,
not a universal physical minimum.

## Implementation and retained failures

[V1](../m10_source_compare_v1/README.md) retains the initial4K100-frame run and the
zero-image2K FAIL. The old instrumented module rejected112 capture requests with
`unexpected_dimensions`; V1's second2K run was NOT RUN. It is not counted as slow2K.
V2 admits only the two declared dimensions. The one-line guard is the only change
in the readback implementation; capture identity, query/poll, allocation, copy,
stream ownership and resource bounds are unchanged. A new pinned module and a new
matched4K baseline were used. No failed client was silently retried.

The2K owner/result/candidate/schema and bounding boxes are separately typed. The
native resize keeps the existing Pillow-equivalent arithmetic and is bit-exact for
all retained RGB inputs. Both resolutions feed the same960×960 model, class vector,
FP32 precision and thresholds. No training, FP16, quantization or board optimization
was performed. Active1/pending-latest1/current1, same-owner3-call preparation,
state100ms and the original acquisition/receipt deadlines are preserved. The finite
240-reference recorder is a Host evidence collector, not a Jetson queue requirement.

## Development quality

| Fixed model, all81 development scenes per arm | 4K | 2K |
| --- | ---: | ---: |
| Ground-truth objects | 129 | 129 |
| TP / FP / FN | 128 /0 /1 | 129 /0 /0 |
| Precision | 100% | 100% |
| Recall | 99.22% | 100% |
| Far target recall | 18/18 | 18/18 |
| Small-object recall, canonical area <32² | 59/60 | 60/60 |
| Rider-person recall | 26/27 | 27/27 |
| Near-person recall | 3/3 | 3/3 |

No measured class/stratum/size/person recall or precision regressed. The one
changed scene was `v9-development-069`: the4K output missed one rider-person;
2K detected it. Both passed the inherited absolute DEVELOPMENT gates. This single
case does not establish superior general accuracy at2K; different source sampling
still yields different960×960 inputs. `quality-comparison.json` retains all paired
count differences and `comparison-*-score.json` includes the full denominators.

The same81 already-consumed development cases at site38 cover three weather
conditions, near/medium/far/occluded targets, small objects, riders and negatives.
Both selected RGB and instance packets are retained; all81 predictions, including
cold/late ones, enter primary quality. Full300 model outputs and tensor hashes are
retained. Unselected/settling frames follow the inherited capture protocol and are
not claimed as archived. No old holdout data was opened and this is not an independent
quality qualification. Offline elapsed/admitted statistics include unpacking and
native/Pillow verification; they must not be used as live latency measurements.

## Evidence, provenance limitation and restoration

The original621-file V1 and626-file V2 freezes remain immutable. A common preflight
and offline derivation helper, `source_compare_v1_common.py`, was accidentally omitted
by the freeze file glob. `supplemental-sources.json` and its separate source archive
preserve that file, sealed after all live runs and4K quality capture, before2K quality
capture. Both live clients use it only to verify files/inputs; quality uses its
preflight and post-capture derivation. Scene definitions, capture probe, timing,
models, algorithms and native binaries are in the original freeze. The supplementary
archive permits full replay but does **not** repair prospective source closure.
`validation.json` therefore records `prospective_source_closure: false` alongside
replay PASS. Do not call this a completely prospectively sealed qualification.

Across V1/V2, all400 delivered live RGB and162 selected quality RGB/instance pairs
are retained:724 raw packets and562 RGB observations.112 report/trace mutations are
rejected (V1:28, V2:84). Python370 and native2K ASan+UBSan3 tests passed; no fresh
unrelated C++ suite is claimed. Fresh-source validation extracts the frozen archive
plus the explicitly supplemental helper; verifies every LFS payload/member/BGRA/RGB;
recomputes exact native/Pillow inputs, GT and scores from the original full outputs;
and replays timestamps, outcomes, original failures and future exclusion union.

V2 preserves 26 LFS archives (5,301,770,240 bytes). Future exclusion
is the exact RGB union:8213→8675; repeated hashes are not assumed novel.
V1 andV2 together preserve28 archives; all received and selected data remain in scope.

All raw LFS objects were explicitly uploaded before removing duplicate temporary
compressed files. `raw-archives.json` maps every object and member. The original
CARLA module was restored before both quality captures. `environment-restoration.json`
verifies the original module and exact original GameUserSettings bytes after all
servers exit. External UE/CARLA source files were not modified; the installed module was changed
only for the declared live trials and then restored.
M10, live20Hz, full consumer freshness, independent quality, actual vehicle control
and per-Jetson deployment remain OPEN.
