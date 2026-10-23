import carla,json,faulthandler
from pathlib import Path
faulthandler.enable()
p=Path("/d/shin/stratadrive-tools/carla-0.9.16/m7-1b/fresh-reset-probe.json")
c=carla.Client("127.0.0.1",2000);c.set_timeout(10)
w=c.get_world();before=w.id
p.write_text(json.dumps({"stage":"before_reload","before":before})+"\n")
w=c.reload_world(False)
p.write_text(json.dumps({"stage":"after_reload","before":before,"after":w.id})+"\n")
print(before,w.id)
