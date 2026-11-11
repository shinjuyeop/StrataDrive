# Native startup V1: one separately declared server recovery

Declared after the original prepared-01 server attempt failed, before the recovery.
The original began2026-11-11T05:24:34.068439+00:00, did not open its RPC port within
180s, and required SIGKILL after the unchanged30s shutdown budget. Exit-9 and
210.79820080194622s elapsed remain FAIL. No client was launched; no sensor, synthetic
model call or RGB acquisition occurred. Logs and original server.json are retained.
The process was observed waiting for file I/O, but this does not establish a root
cause or justify accepting cold startup. No asset prefetch or startup extension is
introduced by this recovery.

Authorize exactly one additional attempt for prepared-01, stored separately as
prepared-01-recovery, after both original attempts have exited and ports2300..2302
are free. Reuse all547 frozen source bytes and identical model, native library,
4K camera, development fixture, preparation,1200..1204 ticks and240 acquisitions,
recorder and observation gates. Reuse startup180s/client900s/shutdown30s and exit130.
No extra warmup/model calls, changed confidence/deadline, new fixture or repeated
recovery. Existing OS page-cache state is uncontrolled and must not be called cold
startup qualification. All recovery RGB, including failure, enter future exclusions.

The intended evidence is two complete live observations if the remaining original
prepared-02 and this recovery succeed. Report the original failure alongside them;
a recovery PASS never rewrites the failed attempt. Original and recovery lifecycle
reports, pre-execution declaration hashes and every acquired raw image are required.
