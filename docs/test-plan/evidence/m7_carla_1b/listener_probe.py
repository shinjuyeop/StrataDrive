import carla,json,time,sys,traceback
from pathlib import Path
p=Path(sys.argv[1]);r={'python':sys.executable,'carla':carla.__file__};w=orig=a=None
try:
 c=carla.Client('127.0.0.1',2000);c.set_timeout(10);w=c.get_world();orig=w.get_settings();s=w.get_settings();s.synchronous_mode=True;s.fixed_delta_seconds=.05;w.apply_settings(s)
 bp=w.get_blueprint_library().find('sensor.camera.rgb');a=w.spawn_actor(bp,carla.Transform(carla.Location(z=2)));r['id']=a.id;r['before']=a.is_listening()
 a.listen(lambda x:None);r['after_listen']=a.is_listening();w.tick(10);a.stop();r['after_stop']=a.is_listening();time.sleep(.1);r['after_wait']=a.is_listening()
except Exception:r['error']=traceback.format_exc()
finally:
 if a is not None:r['destroy']=a.destroy();w.tick(10)
 if orig is not None:w.apply_settings(orig)
 p.write_text(json.dumps(r,indent=2)+'\n');print(r)
