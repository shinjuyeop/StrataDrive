"""Render recorded observations; this does not rerun DDS or assert performance."""
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
plt.rcParams["svg.hashsalt"] = "stratadrive-dds-lifetime"
rows = [r for r in csv.DictReader((ROOT / "lifetime.csv").open()) if r["mode"] == "correct"]
fig, ax = plt.subplots(figsize=(8, 4.4))
for y, row in enumerate(rows):
    start = int(row["acquired_ns"])
    elapsed = lambda key: (int(row[key]) - start) / 1e6
    ax.hlines(y, 0, elapsed("free_ns"), color="#a6a6a6", linewidth=2)
    for key, marker, color, label in [
        ("last_access_ns", "o", "#2166ac", "Last access"),
        ("scope_end_ns", "|", "#1b7837", "Scope end (before asleep)"),
        ("free_ns", "x", "#b2182b", "Entry to Writer free"),
    ]:
        ax.plot(elapsed(key), y, marker=marker, color=color, markersize=7,
                linestyle="none", label=label if y == 0 else None)
ax.set_yticks(range(len(rows)), [f"{r['profile']} #{r['repetition']}" for r in rows])
ax.invert_yaxis()
ax.set_xlabel("Elapsed monotonic time since Writer lookup (ms)")
ax.set_title("Real Writer lifetime: 9 scoped observations")
ax.grid(axis="x", alpha=.2)
ax.legend(loc="upper right", fontsize=8)
fig.text(.5, .01, "TSan runs remain FAIL (2 warnings each). Diagnostic intervals, not timing acceptance.",
         ha="center", fontsize=8)
fig.tight_layout(rect=(0, .04, 1, 1))
output = ROOT / "lifetime.svg"
fig.savefig(output, metadata={"Date": None})
output.write_text("\n".join(line.rstrip() for line in output.read_text().splitlines()) + "\n")
