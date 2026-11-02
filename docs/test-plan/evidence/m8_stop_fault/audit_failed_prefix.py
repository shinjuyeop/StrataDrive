from pathlib import Path
import json,sys
sys.path.insert(0,str(Path('tests/integration/carla').resolve()))
from evidence_io import json_rows
from audit_m7_1r_work import validate,validate_settlement
root=Path('build/m8-stop-fault/hold-protection-01');report=json.loads((root/'result.json').read_text())
assert report['status']=='FAIL'
previous=None;totals=[0.]*4;count=settled=acks=0;max_balance=0
for row in json_rows(root/'trace.jsonl'):
 acks+=int(row.get('settlement_ack',{}).get('ok',False))
 if row['native'].get('settlement'):
  validate_settlement(row,previous,sum(totals));settled+=1
  max_balance=max(max_balance,abs(row['native']['settlement']['balance_j']))
 if 'receipt' in row:
  sums,_,_=validate(row,previous);totals=[x+y for x,y in zip(totals,sums)];count+=1;previous=row
last=row
assert count==settled==acks==report['receipts']==report['settlements']==1898
assert last['index']==1898 and 'receipt' not in last and last['staged']['latched']
assert last['staged']['reason']=='bootstrap_cannot_drive_or_resume'
assert last['native']['admission']['normal_stop'] and 'stop_requests' not in last['native']['native_export']
server=json.loads((root.parent/'server-hold-protection-01.json').read_text());assert server['server_exit']==130
out=dict(status='FAIL_SERIALIZATION_WITH_VERIFIED_COMPLETED_PREFIX',physics=count,settlements=settled,accepted_settlement_acks=acks,max_abs_energy_balance_j=max_balance,blocked_next_interval=1898,missing_original_stop_packets=True,physical_protection_accepted=False,full_native_audit_accepted=False,server_exit=130)
(root.parent/'hold-protection-01-prefix.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
