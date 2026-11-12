# Bounded2K latency improvements;20Hz is not a required outcome

The user explicitly requests reasonable latency reduction, without making20Hz a
mandatory stopping criterion. Keep2560×1536,5:3/FOV90/Epic/postprocessing and the
fixed D-FINE-M960 FP32 model/vector. No training, engine rebuild, source-resolution
change, board-specific optimization, relaxed expiry or automatic production promotion.

Preserve the626-file source-comparison V2 parent and add the omitted common helper
prospectively in this NEW freeze, using the previously published supplemental hash.
Do not repair or relabel the previous provenance gap. Archive all new sources and
import/test them from a fresh extracted root before any live run. Pin model, native
resize, SDK and previous8675-RGB future exclusions. All candidates keep exact native
Pillow tensors; replay all81 prior2K development inputs and all newly received raw.
No new quality qualification or holdout access; full-model quality need not be rerun
because the model and exact inputs are unchanged for a given source image.

Three initial live conditions, one bounded confirmation at most:

| Condition | Tensor construction | Readback | Engine maximum tick rate |
| --- | --- | --- | --- |
| baseline-01 | Original allocation/division/contiguous copy | Blocking query | Existing uncapped behavior |
| tensor-01 | Reusable single-owner float32 NCHW output; same division | Blocking query | Existing uncapped behavior |
| balanced-01 | Reusable exact tensor | Existing deferred option | t.MaxFPS100 |
| confirm-01 | Selected tensor or balanced candidate | Same as selected | Same as selected |

The deferred implementation is already in the pinned source-comparison V2 module;
no C++ implementation change is introduced. Previous uncapped4K deferred failures
remain failures. The engine cap uses the existing Unreal max-tick-rate limiter to
avoid running the10ms simulation much faster than real time; it does not rescale
source timestamps, change simulation delta, tick the world from the client, or
extend deadlines. The actual observed world/camera rates and simulation/wall ratio
must be reported. The cap is a ceiling, not a promised minimum throughput.

Use the inherited500..504-source-frame primary window,300ms camera-silence tail,
actual on_tick clock, original exclusive source/receipt100ms and state100ms,
active1/pending-latest1/current1,3 preparation calls on the same inference owner,
240-reference memory recorder, zero normal measured disk writes and all original
raw retention. Lifecycle180/900/30s, exit130, no hidden client retries. At most one
startup-only recovery per condition is allowed only if no client was started;
preserve both original and recovery reports. A known failure is not rerun unchanged.

Selection is prospective and modest: a candidate must pass original integration
and raw/input checks, improve all-call capture-to-backend mean by at least3ms,
have P95 no worse than baseline×1.05, retain at least95% of baseline camera rate,
and lose no more than5 percentage points of sampled active fresh-read availability.
Balanced must additionally show observed cap100 and simulation/wall ratio≤1.05.
Among eligible candidates choose lower mean, then lower P95, with tensor preferred
if mean separation is less than3ms. Record selection.json before confirm-01 starts.
The confirmation must pass the same eligibility criteria against the same baseline;
otherwise retain the baseline recommendation and report the observed variation.
If neither candidate is eligible, skip confirmation and keep baseline. No changes
to these rules after results; no pursuit of20Hz beyond this four-run bound.

Report capture→backend and first-consumption latency separately, all tails/late
calls, sampled freshness and actual Hz. A result below100ms on average is not an
all-frame/consumer100ms claim. Preserve every FAIL and any performance regression.
Restore the original CARLA module and exact GameUserSettings. New LFS objects must
be hash/member verified and uploaded before removing duplicate temporary raw;
verified cache relocation is permitted with recorded SHA/size and retained symlinks.
Final recommendation is a development configuration, not controller/ROS/Jetson or
long-term real-time qualification. M10 remains OPEN.
