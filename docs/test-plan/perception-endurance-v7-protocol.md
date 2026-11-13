# M10 bounded endurance V7

V6 failed unchanged HV30ms at initial+1135.015ms and later overflowed recorder
queue8. Telemetry observed100C at+0.432s and all sampled cores near0.8GHz at
+1.449s/+2.462s, with increasing package thermal-throttle counters. This supports
a real host thermal bottleneck; the host idle wait alone did not resolve it.
The first failed case is retained and remaining cases are NOT_RUN.

V7 retains the V6 module/idle wait, V4 core placement/NVMe spool and every original
controller/acceptance bound. It opts into ORT intra/inter-op allow_spinning=0,
verified from the live session options. Four intra-op threads, one inter-op
thread, CUDA provider, model, precision, graph and input arithmetic stay fixed.
The official setting controls idle worker CPU use:
https://onnxruntime.ai/docs/performance/tune-performance/threading.html
The default execution policy outside this explicit option is unchanged.

Zstd level1 and exact raw/hash chains remain. Each recording worker reuses its
own compression buffer; string_at copies only the compressed output instead of
copying a full bound-sized buffer and then slicing it. There are still two
workers and queue8; no raw frame or RGB hash is deferred or discarded. Faster
negative compression levels were evaluated offline but not selected because
their sizes exceed the current per-frame storage budget.

Before live execution, three already-excluded V6 images were replayed four times
per policy. All12 decoded object counts/classes matched, maximum score delta was
1.1920929e-7 and box delta6.103515625e-5 in640-coordinate units. Raw output is
NOT bit-exact: low-score candidate order also varied across unchanged-policy
repetitions. Retain both raw numeric outputs; this is not quality promotion or
proof of reduced heat under concurrent rendering. No new camera/holdout data
was used for this check.

Declare three30s cases and conditional300s under the same stop-on-first-failure
rule. All raw callbacks join the V6 exclusion chain. Original physical5ms,
HV30ms,2/4ms checks,100ms freshness and zero accepted perception remain. Host
thermal, power and kernel limits are not modified; cooling is not software-fixed.
