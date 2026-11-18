# Fresh 2K Host quality evaluation

Development uses Town04 spawn 90 (road 29). Holdout uses spawn 101 (road 36).
Selection used only surveyed geometry. Both sites are at least 50 m from the
previous selected Town04 sites and have disjoint sampled road IDs. [Selection](plan/sites.json)

Each partition has 99 separate preparation scenes and 81 evaluation scenes. Both
RGB and instance masks come from 2560×1536, 90° cameras at 100 ms simulated
intervals. Quality uses stationary actors, a synchronous 10 ms simulation step,
40 settling ticks and the first subsequent scheduled exposure. Startup paired
frames fix the exposure phase before scene placement. Timing in this isolated
capture does not measure live control availability.

Preparation must verify original pixel hashes, independent routes and image
health, all planned actors and riders, three primary targets per class and stratum
and all 18 occlusion-reference pairs. A preparation failure stops the partition.
The selected image is fixed before reading pixels or predictions. Every acquired
image from failed attempts is excluded from future independent evaluation.

Both fixed models receive the same original camera exposure. For the YOLOX-S
baseline, reduce the original RGB image to 640×384 using Pillow bilinear
resampling, then use the published baseline input, thresholds and decoder.
D-FINE-M960 receives the native 2K BGRA with the exact CUDA resize. Keep raw
predictions and report quality in the canonical 640×384 coordinates against the
native instance masks. All 81 images, including cold calls and model failures,
belong to the denominator. Scoring uses visible same-class boxes at IoU ≥0.5.

The existing absolute thresholds apply. Precision ≥85%, recall ≥80%, each class
recall ≥70%, near-person recall ≥90% and at most one false positive per three
negative frames. Against the paired baseline, require a precision gain of at
least 3 percentage points, no decrease in overall, class, far or occluded recall
or near-person true positives, and no additional negative false positives.
Development must pass preparation and absolute and relative quality before
nomination. Seal the model, preprocessing, thresholds and development evidence
before capturing holdout evaluation. A failed holdout remains consumed. [Quality thresholds](../../../../profiles/perception-quality-protocol-v9.json)
