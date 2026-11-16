# Read-only host sensor / native wake probe

Declare one unloaded5s native observation using the already tested watch-timing
postfix binary, FIFO18 and CPUs1,9. No CARLA, images, physical receipts, learned
results, controls or acceptance claims. Preserve the original2ms monitor grid
and4ms deadline; retain any failure and do not rerun this sequence until pass.
Observer runs on0,8, sampling the complete IRQ snapshot and coretemp/CPU clocks,
all per-CPU thermal counters, read-only pstate limits and non-Dell cooling states
at50ms. No repeated Dell/SMM polling belongs in this observer.

At native initial+1s read one coretemp temperature as a reference; at+2s,+3s,+4s
read exactly one fan1/fan2/fan3 input from the discovered dell_smm driver. Record
wall brackets and observer thread CPU time for each read. These queries can
invoke firmware and perturb timing; the test is deliberately isolated from
CARLA and physical acceptance. Do not write fan, power, frequency, IRQ or kernel
settings. Retain exact monitor requested/actual timestamps and report correlation
only, not proof that this firmware path caused any earlier loaded failure.

Qualification: maximum coretemp<=70C, at most180s wait before launch. Record code,
protocol and native binary hashes beforehand. Stop native after5s, retain all
records and restore no settings because none are changed. A maximum10s native
initialization and5s exit bound apply. No hardware stress loop is introduced.

References checked2026-11-16:
- https://www.kernel.org/doc/html/latest/hwmon/dell-smm-hwmon.html
  explains the BIOS/SMM query path and possible short hangs.
- https://docs.kernel.org/admin-guide/pm/intel_pstate.html
  defines active-mode scaling_cur_freq as a sampled average P-state, not an
  exact instruction-cycle trace; global performance limits affect every CPU.
