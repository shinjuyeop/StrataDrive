# 2K/4K source comparison V1 — implementation rejection retained

The first 4K observation passed the finite integration checks. The first 2K
attempt failed before receiving an image because the existing instrumented CARLA
module only admitted 3840×2304. This bundle retains the failure; it is not a 2K
performance measurement. [V2](../m10_source_compare_v2/README.md) contains the new
module revision and a new matched 4K baseline.

| Declared run | Original outcome | Received RGB | Camera wall Hz |
| --- | --- | ---: | ---: |
| source-4k-01 | PASS, finite observation only | 100 | 15.556 |
| source-2k-01 | FAIL: unexpected_dimensions | 0 | Not measurable |
| source-2k-02 | NOT RUN: same known module incompatibility | — | — |
| Both quality arms | NOT RUN in V1; moved prospectively to V2 | — | — |

All112 attempted 2K capture requests were rejected before rendering/sending. The
client reported `owner made insufficient progress: camera`; no model calls or
camera offers occurred. The server exited130 without forced termination. The
failure review and original logs remain unchanged. V2 changes only the explicit
readback dimension guard to admit both predeclared sizes and preserves these621
frozen files. There was no hidden retry or relabelling of this FAIL.

The 4K arm retained the fixed D-FINE-M960 FP32 model, Epic/postprocessing/FOV90,
normal immutable bytes copy, original source/receipt100ms and state100ms expiry,
actual snapshot observations and zero client ticks. Its99 model calls include
all cold/late calls;97 published and70 distinct frames were consumed. The sampled
fresh-read fraction was23.22%, not continuous availability or driving acceptance.

`freeze.json` preserves601 parent sources plus20 additive files; `sources.tar.gz`
contains all621 listed files, including both native resize binaries. The freeze glob
omitted `source_compare_v1_common.py` (preflight/quality derivation). Its separate
`supplemental-sources.json` and archive were sealed after the live trials and4K
quality capture. Replay includes this one additional helper, but prospective source
closure remains false; the original freeze is not rewritten. The2K kernel was
checked bit-for-bit against Pillow and with ASan+UBSan. `python-tests.log` and the
sanitizer log record370 Python and3 sanitizer tests. No new generic C++ suite is
claimed by this study. `check-evidence.py` independently extracts the archive,
replays timing/invariants and the zero-delivery failure, verifies every LFS payload,
BGRA/RGB and native model input, and checks future exclusion8113→8213. All100 raw
frames are retained in2 LFS archives (1,718,343,680 bytes); no failed images were
received. `report-mutation-check.json` records the actual rejected mutations.

Payloads were explicitly uploaded before temporary duplicate raw files were
removed. `local-storage.json` records the hash-verified relocation of these two
local LFS objects; their original cache paths are symlinks to retained project-volume
copies. This is storage placement only, not removal of evidence.

`restore.json` records restoration of the original module before the new build.
The V2 final restoration report covers the end of the whole study. No default,
controller, ROS or Jetson deployment was promoted. M10, independent quality,
wall20Hz and real-time1× remain OPEN. The81-case quality material in V2 is already
consumed development data; old holdout data was not opened.
