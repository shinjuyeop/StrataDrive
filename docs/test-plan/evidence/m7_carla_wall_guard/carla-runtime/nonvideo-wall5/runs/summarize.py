from pathlib import Path
import json
root=Path('/d/shin/StrataDrive');w=Path('/d/shin/stratadrive-tools/m7-source/m7-wall-stabilize');out=root/'docs/test-plan/evidence/m7_carla_wall_guard/carla-runtime/nonvideo-wall5'
records=[]
for i in range(1,14):
 p=w/f'run{i:02}';r=json.loads((p/'result.json').read_text());s=json.loads((w/f'server-run{i:02}.json').read_text())
 ap=p/('audit-final.json' if (p/'audit-final.json').exists() else 'audit.json');a=json.loads(ap.read_text()) if ap.exists() else None
 status='PASS_BOUNDED_CASE' if a and a['status']=='PASS_CASE_ONLY' and s['probe_exit']==0 and s['server_exit']==130 else 'FAIL'
 if i==4:status='EXPLORATORY_OLD_AUDIT_ONLY'
 records.append(dict(run=p.name,profile='wall10' if i<=2 else 'nonvideo-wall5',fault_requested=r['fault'],fault_request_observed='fault_request' in r,status=status,probe_exit=s['probe_exit'],server_exit=s['server_exit'],audit=a,result_status=r['status']))
cor=json.loads((w/'audit-corruptions-final.json').read_text());reg=json.loads((w/'regression/suite.json').read_text())
assert len(cor['checks'])==12 and all(x['rejected'] for x in cor['checks'])
assert reg['status']=='COMPLETE_BOUNDED_SUITE'
for name in ['normal-tests-final.log','asan-tests-final.log']:assert '100% tests passed, 0 tests failed out of 118' in (w/name).read_text()
summary=dict(status='EXPERIMENTAL_PARTIAL_SUCCESS_REPEATABILITY_OPEN',base_commit='1215bd6',m6_changed=False,wall_realtime_accepted=False,final_build_normal_intent=dict(cases=['run10','run11'],passed=1,total=2),final_build_fault_intent=dict(cases=['run12','run13'],passed=0,total=2),cases=records,regression=dict(native_normal=dict(passed=118,total=118),native_asan_ubsan=dict(passed=118,total=118),original_10ms_carla=[dict(name=x['name'],status=x['status'],runner_exit=x['exit'],audit_exits=[a['exit'] for a in x['audits']]) for x in reg['cases']],auditor_corruptions=dict(rejected=12,total=12),new_tsan='NOT_RUN',full_m6_suite='NOT_RUN'),remaining=['EV/HV oldest input age crossed original30ms during normal run11; original-time replay reproduced first protection','UE shutdown thread pool SIGSEGV in run02/11/12','long-duration wall and camera wall acceptance not run'],source_unchanged_roots=['central','zone','vecu','interfaces','simulation'])
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(summary['status'],summary['regression'])
