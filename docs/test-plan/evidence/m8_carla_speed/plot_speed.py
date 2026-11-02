import gzip,json,sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
root=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(exist_ok=True,parents=True)
b=[];c=[];seen=set();origin=None
with gzip.open(root/"trace.jsonl.gz","rt") as f:
 for line in f:
  r=json.loads(line);b.append((r["simulation_seconds"],r["physics"]["body_forward_velocity_m_s"]*3.6))
  s=r.get("native",{}).get("speed_control")
  if s and s["sequence"] not in seen:
   seen.add(s["sequence"]);origin=s["origin_ns"]*1e-9;c.append(s)
def ref(t):
 return 0 if t<0 or t>=30 else (t if t<10 else 10 if t<20 else 30-t)
t=[x-origin for x,_ in b];v=[x for _,x in b];ct=[(s["release_ns"]-c[0]["origin_ns"])*1e-9 for s in c]
fig,axs=plt.subplots(3,1,figsize=(10,7),sharex=True,constrained_layout=True)
axs[0].plot(t,[ref(x) for x in t],"--",color="black",label="Target")
axs[0].plot(t,v,color="#1874a6",label="CARLA body")
axs[0].plot([(s["source_ns"]-c[0]["origin_ns"])*1e-9 for s in c],[s["speed_mps"]*3.6 for s in c],color="#c56d19",alpha=.65,label="Drive wheel x 0.355 m")
axs[0].set_ylabel("Speed (km/h)");axs[0].legend(loc="upper right",ncol=3,fontsize=8)
axs[1].plot(t,[y-ref(x) for x,y in zip(t,v)],color="#1874a6");axs[1].set_ylabel("Body error (km/h)")
axs[2].plot(ct,[s["acceleration_mps2"] for s in c],color="#39783b");axs[2].set_ylabel("Request (m/s^2)");axs[2].set_xlabel("Simulation time from first control release (s)")
for ax in axs:
 ax.grid(alpha=.2);ax.set_xlim(-1,40)
 ax.axvspan(15,20,color="#497a3d",alpha=.08);ax.axvspan(35,38,color="#497a3d",alpha=.08)
fig.suptitle("M8 CARLA V1 speed loop — 4,000 physics intervals; simulation-time only")
fig.savefig(out/"speed-tracking.png",dpi=160);fig.savefig(out/"speed-tracking.svg")
