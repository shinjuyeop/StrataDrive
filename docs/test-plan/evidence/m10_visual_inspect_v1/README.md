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

A moving physical scene still needs an authoritative completed-frame association,
render application/readback and native receiver verification. Stationary ordinal
samples alone cannot establish that association.

The third attempt passed both server sessions and verified restoration. All
16 paired actor samples again had zero differences across the recorded fields.
Eight original 2560×1536 camera exposures matched their local renderer frames
and source times. The seven frame increments were 3, 2, 2, 2, 2, 2 and 2.
Archive replay independently recovered all eight compressed BGRA payloads and
matched the stored-data, original BGRA and RGB hashes.
[Field comparison](parked-comparison-03.json) · [Archive manifest](pair-03/manifest.json)
