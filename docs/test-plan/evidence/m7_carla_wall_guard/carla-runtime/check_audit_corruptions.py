import copy,json,pathlib,sys
sys.path.insert(0,str(pathlib.Path.cwd()/'tests/integration/carla'))
import audit_m7_wall_carla as module
root=pathlib.Path('/d/shin/stratadrive-tools/m7-source/m7-wall-carla');directory=root/'run24'
base=module.audit(directory);assert base['status']=='NOT_ACCEPTED'
(directory/'audit-final.json').write_text(json.dumps(base,indent=2)+'\n')
rows=[json.loads(x) for x in (directory/'trace.jsonl').read_text().splitlines()]
index=next(i for i,x in enumerate(rows) if not x['receipt']['original_actual']['admitted_actual']['empty_init'])
def crc(r):
 s=r[index]['receipt']['original_actual']['native']['actual'][0]
 r[index]['receipt']['original_actual']['native']['actual'][0]=s[:-2]+('00' if s[-2:]!='00' else '01')
mutations={
 'owner_wire_crc':crc,
 'future_acquisition':lambda r:r[0]['receipt'].update(physics_acquisition_begin_ns=str(int(r[0]['receipt']['physics_acquisition_end_ns'])+1)),
 'model_interval':lambda r:r[0]['receipt'].update(logical_end_ns=str(int(r[0]['receipt']['logical_end_ns'])+1)),
 'unbacked_effort':lambda r:r[0]['receipt']['physics']['wheels'][2].update(set_drive_nm=1),
 'raw_negative_wheel':lambda r:r[0]['receipt']['physics']['wheels'][2].update(solver_omega_rad_s=-.00001),
 'raw_solver_change':lambda r:r[0]['raw_solver']['trace']['steps'][0]['after_rad_s'].__setitem__(2,999),
 'missing_completed_work':lambda r:r[0].update(settlement=None),
 'energy_imbalance':lambda r:r[0]['settlement'].update(balance_j=1),
}
original=module.read;results={}
for name,mutate in mutations.items():
 changed=copy.deepcopy(rows);mutate(changed)
 replacement='\n'.join(json.dumps(r) for r in changed)
 module.read=lambda path:replacement if path.name=='trace.jsonl' else original(path)
 try:module.audit(directory)
 except ValueError as e:results[name]=str(e)
 else:raise AssertionError('corruption accepted: '+name)
 finally:module.read=original
out={'status':'PASS_REJECTION_ONLY','baseline_status':base['status'],'rejected':results,'full_m7_closed':False}
(root/'audit-corruptions.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
