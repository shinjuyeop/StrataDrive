import subprocess,runpy,pathlib,json,sys,hashlib
root=pathlib.Path('/d/shin/stratadrive-tools/m7-source/m7-wall-carla');args=json.loads((root/'run12-args.json').read_text())[2:]
args[args.index('--runtime')+1]=str(root/'runtime19');args[args.index('--output')+1]=str(root/'run19')
original=subprocess.Popen

def wrapped(argv,*pos,**kw):
 if isinstance(argv,list) and str(argv[0]).endswith('/UE4Editor'):
  env=dict(kw['env']);assert not env.get('LD_PRELOAD');env['LD_PRELOAD']=str(root/'pc_sample.so');env['M7_PC_TRACE']=str(root/'run19-pc.csv');kw['env']=env
 return original(argv,*pos,**kw)
subprocess.Popen=wrapped;sys.argv=['tests/integration/carla/m7_1o_run.py']+args
(root/'run19-sampler.json').write_text(json.dumps({'status':'DIAGNOSTIC_ONLY_NOT_TIMING_ACCEPTANCE','sampler_sha256':hashlib.sha256((root/'pc_sample.so').read_bytes()).hexdigest(),'period_ns':500000},indent=2))
runpy.run_path(sys.argv[0],run_name='__main__')
