# Model artifact policy

Status: M0 policy; no models are included or downloaded.

Large datasets, weights, exported ONNX files and device-specific TensorRT engines
belong outside Git. Record source/license, checksum, model version, export settings,
calibration provenance and compatible runtime/hardware in a future artifact manifest.
Do not assume an engine built for one board works on the other.

`.gitignore` excludes `models/*`, `*.pt`, `*.pth`, `*.onnx`, `*.engine` and `*.plan`
by default. These are reviewable defaults, not a permanent ban on small examples.
For a deliberately reviewed, redistributable small fixture, add an exact exception
at the **end** of `.gitignore`, for example:

```gitignore
!models/samples/
models/samples/*
!models/samples/tiny-reviewed.onnx
```

Before adding it, document size, license, source, checksum and why the test needs it.
A size threshold and any external storage/Git LFS policy remain TBD. Do not broadly
unignore a whole model directory or routinely use `git add -f`. Ignored dataset
folders similarly need explicit parent exceptions if a README is later tracked.
