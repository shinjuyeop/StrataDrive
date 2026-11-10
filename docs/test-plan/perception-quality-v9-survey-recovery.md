# V9 map-survey shutdown recovery

The original survey-01 completed372 map-only queries and selected38/85, with
client exit0, but the UE process did not exit within30s after SIGINT. The harness
forced SIGKILL and recorded server exit−9/statusFAIL. There were no cameras,
RGB, instance images or model inference. Keep that failure and its full logs.

Before the second launch, bind the original server/survey hashes and original
survey source freeze. Permit exactly one additional isolated full map survey,
using the identical source, used-road descriptor, command,180/900/30s bounds,
port guards and expected normal exit130. No selection/geometry/quality/model
setting changes or post-query waiting-budget extension. The map-selection
algorithm remains first complete unused routes; the failed query cannot be
relabelled accepted. Only a separately successful second server/query may supply
the plan. Preserve both query outputs and include this annex/recovery record in
the later preparation/quality freeze. This does not resolve the UE shutdown
root cause or qualify startup/shutdown reliability.
