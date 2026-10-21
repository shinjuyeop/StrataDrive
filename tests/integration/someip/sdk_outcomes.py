"""Expected injected transport loss is separate from an unexpected SDK failure.
No sanitizer output is classified here. No log is removed or rewritten.
"""
import csv
from datetime import datetime, timezone, timedelta
from pathlib import Path
import re

RESET = re.compile(r'\[error\] tcei::write_completion_condition: Connection reset by peer\(104\) bytes transferred: 0 bytes to sent: 101 remote:10\.88\.0\.2:30502 \(1311\): \[5345\.0050\.[0-9a-fA-F]{4}\]$')

def expected_injected_lease_reset(line, filename, result, folder):
    if result.get('case')!='restart-live' or filename!='central-1.stdout' or not RESET.search(line):return None
    crash=result.get('injected_crash',{})
    if crash.get('role')!='front' or crash.get('generation')!=1:return None
    rows=result.get('processes',[])
    if not any(r.get('role')=='front' and r.get('generation')==1 and r.get('expected_abrupt_stop') is True for r in rows):return None
    central=next((r.get('summary',{}) for r in rows if r.get('role')=='central'),{})
    if not (result.get('surviving_central_rejoined') and central.get('pass') is True and central.get('epoch',0)>1 and central.get('release_ack_mask')==255 and central.get('diagnostic_rejected')==1 and central.get('batches',0)>=10):return None
    try:
        sample=result['clock_sample']
        stamp=datetime.strptime(line[:26],'%Y-%m-%d %H:%M:%S.%f').replace(tzinfo=timezone(timedelta(seconds=sample['utc_offset_s'])))
        event_ns=int(stamp.timestamp()*1e9)-sample['wall_ns']+sample['monotonic_ns']
        # The predicate also requires exact socket, service, method, payload size,
        # injected SIGKILL, a live original credit, observed protection and rejoin.
        if not 0<=event_ns-crash['ns']<=100_000_000:return None
        protected=int((Path(folder)/'central-protected').read_text())
        if not 0<=protected-crash['ns']<=100_000_000:return None
        with (Path(folder)/'central-1.events.csv').open() as stream:
            credits=[r for r in csv.DictReader(stream) if r['event']=='credit-issued' and int(r['epoch'])==1 and int(r['ns'])<=event_ns+1_000_000 and int(r['deadline'])>crash['ns']]
        if not credits:return None
        credit=credits[-1]
        return {'classification':'expected injected Front crash: original RunLease send reset',
                'event_monotonic_ns':event_ns,'protection_ns':protected,'credit_sequence':int(credit['value']),
                'original_credit_expiry_ns':int(credit['deadline']),'bytes_not_sent':101}
    except (KeyError,ValueError,OSError):return None

def sdk_outcomes(folder,result):
    expected=[];unexpected=[]
    for path in sorted(Path(folder).glob('*.stdout')):
        for number,line in enumerate(path.read_text(errors='replace').splitlines(),1):
            if '[error]' not in line:continue
            row={'file':path.name,'line':number,'text':line}
            reason=expected_injected_lease_reset(line,path.name,result,folder)
            if reason:expected.append(dict(row,**reason))
            else:unexpected.append(row)
    return expected,unexpected
