# Visual state in two parked worlds

The physical world and renderer each exposed 16 consecutive frames of the same
three stationary actor recipes at matching spawn points. Each RPC was bracketed
by two SDK snapshots of that world's own frame and source time. These runs had
no native START or vehicle control.

| Actor | Compared components | Bones | Material slots |
| --- | ---: | ---: | ---: |
| Lincoln MKZ 2020 | 57 | 9 | 33 |
| Tesla Model 3 | 32 | 5 | 8 |
| Pedestrian 0001 | 5 | 66 | 18 |

The comparison resolves instance-local material objects to their parent assets
and compares all recorded scalar, vector and texture parameters. The measured
fields matched on every paired ordinal sample. Both cars expose all four named
wheel bones. The renderer has additional semantic-tag proxies on 26, 2 and 1
components respectively. They are enumerated separately. The comparison records
hashes for the 91 directly named packages, including the map. Transitive package
dependencies and live changing light settings are outside this inspection.
[Measured fields, assets and identities](parked-comparison-02.json)

The first attempt ended during cold map load. In the second attempt both worlds
produced all 16 component snapshots. The renderer client then stopped on an
assumption that consecutive callback frame IDs always differed by exactly two.
One lossless camera packet was retained. The original renderer verdict is FAIL.
Both servers exited normally in the second attempt. The six shared runtime files
matched their original hashes. [Original second attempt](pair-02/result.json)

The third attempt passed both server sessions and verified restoration. All
16 paired actor samples again had zero differences across the recorded fields.
Eight original 2560×1536 camera exposures matched their local renderer frames
and source times. The seven frame increments were 3, 2, 2, 2, 2, 2 and 2.
Archive replay independently recovered all eight compressed BGRA payloads and
matched the stored-data, original BGRA and RGB hashes.
[Field comparison](parked-comparison-03.json) · [Archive manifest](pair-03/manifest.json)

## Moving physical source and separate camera

The wheel-enabled native fixture completed 400 physical intervals and 400
energy settlements. Sixteen selected frames held the original authenticated
physics receipt and the observed scene. Ego travelled 1.8495 m and its four
wheel bones had 16 distinct measured transforms each. The first run used an
executable without wheel support and ended before the first physical interval.
An early replay used the traffic-light cache from preparation and stopped before
camera creation. Later runs observed the frozen red lights at each completed
physical sample. [Source](completed-source-03/result.json) · [Initial replay](completed-replay-01/result.json)

A separate renderer replayed those 16 samples with original actor attributes,
poses and measured PhysX wheel inputs. The 16 actual 2560×1536 exposures each
joined to one physical receipt. Offline decoding recovered every BGRA and RGB
hash. Categorical component differences were zero. The largest ego wheel
difference was 0.1732 cm and 2.0387° when applying the current solver readings.
This simulation-time replay produced zero live native perception admissions.
[Comparison](moving-comparison-02.json) · [Renderer manifest](completed-replay-02/manifest.json)

The next source read the four wheel offsets used by the completed animation
graph. On the independent camera exposures the maximum ego wheel errors fell
to 0.00010 cm and 0.000033°. All 16 images, original receipts, ticket IDs and
RGB hashes were verified. The original actor acquisition bracket in this run
ends just before the wheel accessor, while the same simulation frame remained
held for the whole request. [Moving replay](moving-comparison-03.json)

A separate simulation-time fault test closed the actual perception IPC peer
as the vehicle accelerated. The native receiver observed the disconnect,
requested the existing protective response, and the following frame admitted
braking. The vehicle body and all four wheels reached zero speed. The source
completed 400 physical intervals and 400 energy settlements. The peer had
supplied no detection. This covers transport loss during motion. Normal visual
input and its expiry still require a live, qualified result.
[Transport-loss evidence](transport-loss-01/result.json)

The repeated disconnect test included the wheel read in the measured source
acquisition bracket. The moving vehicle entered the fault at 0.429 m/s. At the
next 10 ms physical stage the brake pressure reached 40 kPa while torque
started its controlled rundown from 300 to 284 N·m. Torque reached zero after
16 stages. The body and all four wheels reached and held zero speed after
0.80 s of simulated time. All 400 physical receipts joined to the immediately
following original energy settlements. Reset required a new INIT and the new
binding rejected advancement without a newly staged input.
[Original-response replay](transport-loss-02/physical-response.json) · [Original-repeat comparison](transport-loss-01/physical-response.json)

A second process rendered all 16 sampled source frames across this stop. Their
original 2K image hashes were recovered. On the sampled exposures, categorical
component fields matched and maximum ego wheel angular error was 0.000030°.
The renderer rejected the wrong key and duplicate wheel names. The six shared
runtime hashes and the original boot-cache file were restored.
[Across-stop replay](transport-comparison-01.json) · [Restoration](transport-runtime-restoration.json)
