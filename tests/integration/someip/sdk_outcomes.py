"""Expected injected transport loss is separate from an unexpected SDK failure.
No sanitizer output is classified here. No log is removed or rewritten.
"""
import csv
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import re

RESET = re.compile(r'\[error\] tcei::write_completion_condition: Connection reset by peer\(104\) bytes transferred: 0 bytes to sent: 101 remote:10\.88\.0\.2:30502 \(1311\): \[5345\.0050\.[0-9a-fA-F]{4}\]$')
RETIRED_CENTRAL = re.compile(r'(?P<role>front|rear) \[error\] tcei::write_completion_condition: (?P<error>Connection reset by peer\(104\)|Broken pipe\(32\)) bytes transferred: 0 bytes to sent: (?P<bytes>[0-9]+) remote:10\.88\.0\.1:(?P<port>[0-9]+) \((?P<client>[0-9a-fA-F]{4})\): \[(?P<service>[0-9a-fA-F]{4})\.0070\.[0-9a-fA-F]{4}\]$')


def expected_retired_central_connection(line, filename, result, folder):
    """An injected peer death may be observed before local protection finishes.

    Classify only old-generation feedback writes; still require both surviving
    owners' protection, physical response and real successor rejoin. This does
    not judge the later service scenario or excuse any missed command deadline.
    """
    match=RETIRED_CENTRAL.search(line)
    if not match or result.get('case')!='central-rejoin' or result.get('forced_cleanup') or result.get('capture_forced_cleanup'):return None
    role=match['role']
    route={'front':('30503','1422','5346'),'rear':('30507','1522','534a')}[role]
    if filename!=role+'-1.stdout' or tuple(match[k].lower() for k in ('port','client','service'))!=route:return None
    # Owner payload <=512 plus the 16-byte SOME/IP header. CRC/binding and
    # complete delivery remain independently checked by the scenario auditors.
    if not 16<int(match['bytes'])<=528:return None
    crash=result.get('injected_crash',{});rows=result.get('processes',[])
    if crash.get('role')!='central' or crash.get('generation')!=1:return None
    if not any(r.get('role')=='central' and r.get('generation')==1 and
               r.get('expected_abrupt_stop') is True and r.get('exit')==-9 for r in rows):return None
    before=result.get('survivor_pids_before',{});after=result.get('survivor_pids_after',{})
    if not result.get('central_rejoined') or before!=after or set(after)!={'front','rear'}:return None
    for peer in ('front','rear'):
        survivor=next((r for r in rows if r.get('role')==peer and r.get('generation')==1),{})
        if (survivor.get('exit')!=0 or
            survivor.get('summary',{}).get('pass') is not True or
            survivor.get('summary',{}).get('orderly_stop') is not True):return None
    try:
        root=Path(folder);sample=result['clock_sample']
        if any(json.loads((root/(p+'.runtime.json')).read_text())['pid']!=after[p] for p in ('front','rear')):return None
        successor_process=next((r for r in rows if r.get('role')=='central' and r.get('generation')==2),{})
        if successor_process.get('summary',{}).get('epoch',0)<2 or successor_process.get('summary',{}).get('release_ack_mask')!=255:return None
        stamp=datetime.strptime(line[:26],'%Y-%m-%d %H:%M:%S.%f').replace(tzinfo=timezone(timedelta(seconds=sample['utc_offset_s'])))
        elapsed=stamp-datetime(1970,1,1,tzinfo=timezone.utc)
        wall_ns=(elapsed.days*86400+elapsed.seconds)*1_000_000_000+elapsed.microseconds*1000
        ns=wall_ns-sample['wall_ns']+sample['monotonic_ns']
        successor=json.loads((root/'native-diagnostics/central/central-2.producer.json').read_text())
        protected={p:int((root/(p+'-protected')).read_text()) for p in ('front','rear')}
        physical=int((root/'physical-protected').read_text())
        if not (successor['generation']==2 and successor['previous_unclean'] is True and
                crash['ns']<=ns<successor['boot_ns']):return None
        if not all(crash['ns']<=t<successor['boot_ns'] and t-crash['ns']<=100_000_000
                   for t in (*protected.values(),physical)):return None
        return {'classification':'expected injected Central crash: feedback to retired generation',
                'event_monotonic_ns':ns,'protection_ns':protected,'physical_protection_ns':physical,
                'successor_boot_ns':successor['boot_ns'],'bytes_not_sent':int(match['bytes']),
                'rule':'retired-central-feedback-v2'}
    except (KeyError,ValueError,OSError):return None

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
            reason=expected_injected_lease_reset(line,path.name,result,folder) or expected_retired_central_connection(line,path.name,result,folder)
            if reason:expected.append(dict(row,**reason))
            else:unexpected.append(row)
    return expected,unexpected
