# Endurance archive processing

The original archive path repeatedly read large uncompressed BGRA tar files from
HDD. The new optional path hashes/copies each source once into lossless gzip,
fsyncs, then independently reads/decompresses the destination. It verifies the
stored transport, the entire original expanded tar (including padding/footer),
every member and every stored/BGRA/RGB image hash. No live recording path changes.

The initial uncompressed streaming checker independently reproduced the original
281-image short-run result. Its exact sources remain in
`uncompressed-check-prototype/`. Subsequent gzip/original-name compatibility and
corruption tests passed20 cases. `compressed-sample.json` proves exact recovery of
one original17-image,267397120-byte shard, including all original image hashes.
The frozen physical auditor still independently reads/checks the original images.

Compression is explicit via `--compress-raw-transport`; the default sealer keeps
its existing transport. Current service-half evidence finished with its original
checker. The CUDA comparison declares the new transport before its first run.
