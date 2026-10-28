import subprocess,runpy,os,ctypes,time,threading,pathlib,json,sys
root=pathlib.Path('/d/shin/stratadrive-tools/m7-source/m7-wall-carla')
args=json.loads((root/'run12-args.json').read_text())[2:]
args[args.index('--runtime')+1]=str(root/'runtime13');args[args.index('--output')+1]=str(root/'run13')
original=subprocess.Popen;sampler=None

def wrapped(argv,*pos,**kw):
 global sampler
 is_server=isinstance(argv,list) and str(argv[0]).endswith('/UE4Editor')
 if is_server:
  parent=os.getpid()
  def allow():
   libc=ctypes.CDLL(None,use_errno=True)
   if libc.prctl(0x59616d61,parent,0,0,0)!=0:raise OSError(ctypes.get_errno(),'owned debugger')
  kw['preexec_fn']=allow
 process=original(argv,*pos,**kw)
 if is_server:
  def collect():
   path=root/'run13/wall-signal';deadline=time.monotonic()+60
   while not path.exists() and time.monotonic()<deadline and process.poll() is None:time.sleep(.01)
   if not path.exists():return
   with (root/'run13-strace.log').open('w') as log:
    debug=original(['strace','-ttt','-T','-e','trace=clock_nanosleep,nanosleep,futex,sched_yield','-p',str(process.pid)],stdout=log,stderr=subprocess.STDOUT)
    time.sleep(2);debug.send_signal(2);debug.wait(timeout=5)
  sampler=threading.Thread(target=collect);sampler.start()
 return process
subprocess.Popen=wrapped
sys.argv=['tests/integration/carla/m7_1o_run.py']+args
try:runpy.run_path(sys.argv[0],run_name='__main__')
finally:
 if sampler:sampler.join(timeout=10)
