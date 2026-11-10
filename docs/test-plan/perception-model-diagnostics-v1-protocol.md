# M10 pretrained detector diagnostics V1

This is descriptive development analysis after model-screen V2, not a new
acceptance run. Keep every V2 checkpoint, export, source, threshold, prediction,
GT, gate and selection byte unchanged. No training, new RGB, holdout access,
runtime promotion or Jetson optimization is authorized by this diagnostic.

## Fixed inputs

Use only the V2 allowlisted development partitions: V4g/V5b/V6/V7 calibration
(324 frames, 516 positive GT) and the already consumed V8 Town04 development
(81 frames, 129 positive GT). Diagnose D-FINE-M and RT-DETRv4-S at their sealed
0.50 confidence; retain S/L development summaries as context. Validate V2 source
freeze, dataset seals, run/model/selection hashes, raw-cache hashes and complete
row lineage before using inputs. Bind this protocol and new diagnostic source
to a separate freeze before computing error aggregates.

## Matching and geometric descriptions

Reconstruct the exact existing stable score-ordered, class-exact IoU0.5 greedy
matching, and check every count and matched GT index against the frozen primary
scorer. Every original FP and FN remains an error; diagnostics do not remove
excluded-overlap FP or change the positive denominator.

For each unmatched prediction record its score/class/box and overlaps against
all positive and excluded GT. Assign one mutually exclusive *geometric* bucket:

1. same-class IoU≥0.5 against an already matched GT (duplicate geometry);
2. other-class positive IoU≥0.5;
3. same-class positive IoU in[0.1,0.5);
4. only other-class positive IoU in[0.1,0.5);
5. no positive IoU≥0.1.

Also retain independent same/other class maxima, all IoU≥0.1 relationships,
excluded overlap, same-actor instance identity and Rider tags. Other-class
overlap is not proof of semantic confusion: Rider/person and bicycle/motorcycle
GT can overlap. "No positive overlap" does not establish that a pictured object
is semantically background or that the annotations cover every world asset.
The original annotation policy is unchanged; visual review can flag uncertainty.

For each unmatched GT examine all native exported top300 rows, including scores
below0.10 and all80 classes, after the same image-coordinate clipping/degenerate
box rejection. Report one exclusive description:

- same-class IoU≥0.5 at confidence≥0.50 but not matched: matching competition;
- same-class IoU≥0.5 only below0.50: excluded by the selected threshold;
- no same-class IoU≥0.5, but some same-class IoU≥0.1: localization overlap;
- no same-class IoU≥0.1 in the native exported top300.

Record best same-class IoU, highest score at IoU≥0.5, best other-class overlap,
native top300 cutoff, and whether any matching proposal is below0.10. These are
observations on the native export, not claims that the full neural head never
produced a box/class. Measure maximum-cardinality one-to-one GT/proposal matching
at score0 as an optimistic recall bound on these native outputs, ignoring FP,
runtime capacity and the primary scorer's greedy ordering. Never reuse one
proposal for multiple GT when computing that bound.

Summarize both error types by dataset, class, weather, stratum, Rider versus
other person, confidence, and fixed tight-GT box-area bins <32², [32²,96²), ≥96²
pixels. Report intersections and examples with counts, not just selected images.
The bins are descriptive and do not establish the cause of a miss.

## Follow-up and verification

Select visual examples deterministically by bucket/class/dataset/scene/index,
with high-confidence FP examples sorted by score then the same identity. Show
unaltered RGB with GT/prediction overlays and clearly label display-only zooms.
Visual uncertainty never silently changes GT, thresholds, counts or nomination.

If native top300 cannot distinguish score ranking from proposal localization,
an annex may expose the original upstream full head on fixed development probes
using the same pinned weights. Preserve native top300 outputs and check numerical
agreement first. Such probes are diagnostics, not a new candidate evaluation.

Tests must cover duplicate versus class-overlap ambiguity, threshold boundaries,
clipping, missing native classes, invalid low-score raw values, and one-proposal
matching competition. Replay aggregates from an archived fresh-source subprocess;
retain hashes for every consumed raw output and development input. Report whether
confidence-only adjustment could meet recall even under the optimistic bound.
Any actual follow-up threshold/input/model experiment needs its own predeclared
development selection rule and new evidence version; V2 settings remain sealed.
Final adoption still requires a new quality protocol and newly acquired holdout.
