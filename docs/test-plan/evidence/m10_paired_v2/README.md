# M10 paired V2: retained preparation failures; paired trial not started

2026-11-13. The paired implementation joins an original native physics receipt to
the same-frame immutable SDK actor snapshot, exports three actor roots through
the bounded scene mailbox, and checks cloned actor and camera transforms in a
separate2K renderer. D-FINE diagnostics cannot publish perception results to the
native controller. Complete wheel/bone/material scene state remains unavailable.

The current1334-file freeze includes the correction for CARLA's uppercase,
hyphenated run UUID. Its source archive passes38 focused checks; the workspace
regression passes451 tests. `preflight-freeze-01` preserves the superseded unused
freeze. `preflight-receipt-clock.json` checks exact source-time agreement across
all400 original owner receipts. These checks do not establish live concurrency.

Preparation failures are retained independently of a driving trial:

| Phase | Outcome | Evidence |
|---|---|---|
| Standard renderer cache preparation01 |900s readiness timeout; forced stop after original30s; thread capture retained | `cache-preparation-01.tar.gz` |
| Standard renderer cache preparation02 | SIGSEGV at first rendered frame, in `FDistanceFieldVolumeTexture::IsValidDistanceFieldVolume`; shader compilation still pending | `cache-preparation-02.tar.gz` |
| Town03 DDC commandlet01 | Available memory fell below2GiB; SIGINT then forced stop after30s | `ddc-preparation-01.tar.gz` |
| Synchronous distance-field preparation01 | Map load1972.355s; same distance-field SIGSEGV at frame2 with `r.AOAsyncBuildQueue=0` confirmed | `sync-cache-preparation-01.tar.gz` |
| Original-profile cache check01 | Early persistent SDK client never observed readiness within300s; independent fresh client observed frames11573→11579 and no sensor/vehicle/walker actors; server exit130 in15.786s | `original-profile-cache-check-01.tar.gz` |

All phases created zero camera packets and ran no native driving interval.
The DDC archive includes its memory guard and a post-run hash check showing all10
selected map packages unchanged. Its minimum sampled available memory was about
598MiB. Original INI bytes were restored. No engine binary, controller deadline,
render quality profile or model arithmetic was changed.

Synchronous construction did not eliminate the crash, so an asynchronous builder
alone is not established as its cause. The original-profile restart subsequently
rendered thousands of frames while remaining derived tasks completed. Its fresh
client observation and bounded post-SIGINT thread capture are preserved alongside
the preparation monitor's original FAIL. The monitor failure is not relabelled.

Neither `prepare-then-normal.py` nor `prepare-then-normal-02.py` admitted a paired
attempt; there is no `case.json` or native driving/camera trial for this freeze.
V3 changes startup checking to finite fresh SDK subprocesses, and waits for both
distance-field and shader workers to finish in separate cache preparation. Native
and perception deadlines are unchanged. No successful simultaneous execution is
claimed by V2; future image exclusion remains9035.
