"""Relate the first original expiry to collection/purge stamps and exact gate replay."""
import json
from pathlib import Path
SERIES=Path(__file__).resolve().parent;BUNDLE=SERIES/'normal-300s-01'
read=lambda name:json.loads((BUNDLE/name).read_text())
fault=read('first-fault-analysis.json')['original_first_fault'];gc=read('gc-analysis.json');replay=read('admission-replay.json')
assert replay['original_native_replay_exact'] and replay['original_proof_bytes_equal']
first=fault['observed_ns'];held=fault['held_hv'];expiry=held['dependency_ns']+fault['hv_dependency_age_ns']
cycle=max((c for c in gc['cycles'] if c['end']['wall_ns']<first),key=lambda c:c['end']['wall_ns'])
index=gc['cycles'].index(cycle);purge=gc['incremental_purge']['cycles'][index]
assert cycle['completed_frame']==held['sequence']
windows={}
for kind in ('Q','R','Z'):
 queries=[q for q in replay['queries'] if q['kind']==kind and cycle['end']['wall_ns']<=int(q['at'])<first]
 accepted=[q for q in queries if q['accepted']=='1']
 windows[kind]=dict(queries=len(queries),accepted=len(accepted),first_accepted_ns=min((int(q['at']) for q in accepted),default=None),last_accepted_ns=max((int(q['at']) for q in accepted),default=None),rejection_reasons=sorted({q['reason'] for q in queries if q['accepted']!='1'}))
result=dict(status='RECORDED_ORIGINAL_EXPIRY_WINDOW',original_first_fault=fault,collection=cycle,purge=purge,
 inherited_dependency_age_ns=held['source_ns']-held['dependency_ns'],dependency_age_at_collection_start_ns=cycle['begin']['wall_ns']-held['dependency_ns'],remaining_age_after_collection_ns=expiry-cycle['end']['wall_ns'],purge_start_after_collection_ns=int(purge['first']['wall_ns'])-cycle['end']['wall_ns'],remaining_age_at_purge_start_ns=expiry-int(purge['first']['wall_ns']),fault_after_collection_ns=first-cycle['end']['wall_ns'],original_admissions=replay['original_admissions'],original_ingress=replay['original_ingress'],counterfactual_post_gc_queries=windows,
 interpretation='Incremental work drained with bounded observed calls, but original held HV expiry remained after the main collection. Query probes are read-only counterfactuals on original inputs, not observed polls or proof of recovery under another CPU layout. The original FAIL is preserved.')
(BUNDLE/'expiry-window-analysis.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['dependency_age_at_collection_start_ns','remaining_age_after_collection_ns','purge_start_after_collection_ns','remaining_age_at_purge_start_ns','counterfactual_post_gc_queries']}))
