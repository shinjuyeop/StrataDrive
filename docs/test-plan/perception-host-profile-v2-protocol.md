# M10 Host profiling V2: verified threads, split placement and raw spool

V1 A and B remain original FAILs. A retained299 images/291 calls and0.700s normal;
B retained299 images/290 calls and2.460s normal. Both exact replays and archive
checks pass, without changing the original failed physical verdicts.

The B report exposed an implementation mistake: the backend constructor reset
OpenCV to4 after the requested2 was applied. Its actual recorded value is4. B
cannot be described as an OpenCV2 measurement. Retain that error and its original
frozen sources. The original V1 C was NOT_RUN. Apply future overrides after backend
construction and verify the resulting setting. This V2 uses OpenCV4 explicitly,
matching B's actual policy so the placement/storage comparisons remain meaningful.

Declare two distinct 30s diagnostic cases, with one attempt each:

- C split: same preparation parking, renderer MaxFPS60, CUDA blocking wait,
  passive ORT and resize4 as B; explicit OpenCV4; Host V3 separates renderer
  cores4–5 from image pipeline cores6–7. Preserve lossless Zstd1 recording.
- D raw shared: B's shared Host V1 and explicit OpenCV4; retain raw BGRA directly
  in NVMe tar shards instead of compressing during control execution. All actual
  BGRA bytes including alpha, BGRA/RGB/stored hashes, original acquisition times,
  every generated callback and every numerical output remain checked/retained.
  The stored and raw byte arrays are identical, so compute their common hash once.

Raw storage trades space/bandwidth for CPU time. Existing frame/queue8/two-worker
limits and total stored-byte/reserve limits remain unchanged. Raw mode is explicit
and restricted to the declared10Hz wall-paced endurance camera. Roughly300 frames
occupy4.72GB, within the original30s byte budget; an overflow still fails. Readers
reject unknown codecs or changed lengths. The auditor requires the declared codec
and the same decompressed/original byte and RGB hashes. No lossy representation,
sampling, dropped image, delayed hash or image-quality evaluation is introduced.

Everything else follows V1: original5ms/30ms/2ms/4ms/100ms control bounds,2K/Epic,
actual camera10Hz, source query20Hz, unchanged numerical model and unavailable
perception. Keep all failures. Sample thread/host/GPU cost across preparation and
execution; zero schedstat wait is not evidence without sched_schedstats. Use the
same compiled module and DXC candidate, freeze new sources before C, and restore
all original runtime hashes afterwards. No 300s case or M10 closure is claimed.
