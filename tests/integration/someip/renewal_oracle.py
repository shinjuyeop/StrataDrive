"""Offline actual-Leaf renewal checks; no timing/authority repair."""
import csv
from pathlib import Path


def renewal_oracle(folder):
    folder=Path(folder)
    out={'pass':True,'errors':[],'leaves':[]}
    def require(ok,why):
        if not ok:out['pass']=False;out['errors'].append(why)
    def read(name):
        with (folder/name).open() as f:return list(csv.DictReader(f))
    margins=[]
    try:
        tx=[r for r in read('central-1.transport.csv') if r['event']=='central-enqueued' and int(r['operation'])==3]
        for owner,role,peer in [(2,'front',0),(3,'front',0),(4,'central',1)]:
            sent={(int(r['epoch']),int(r['payload_source'])):r for r in tx if int(r['peer'])==peer}
            events=read(role+'-1.leaf-events.csv')
            received=[r for r in events if int(r['owner'])==owner and r['event']=='valid-input' and int(r['detail'])==1]
            require(len(received)>=10 and len(received)==len(sent),'command count/missing Leaf '+str(owner))
            seen=set();previous=None;minimum=None
            for r in sorted(received,key=lambda r:int(r['ns'])):
                key=(int(r['epoch']),int(r['source']));request=sent.get(key)
                require(request is not None and key not in seen,'unknown/duplicate accepted Leaf command '+str(owner));seen.add(key)
                if request:
                    require(int(r['deadline'])==int(request['inner_deadline']),'changed original command expiry '+str(owner))
                    require(int(request['sent'])<=int(r['ns'])<int(request['deadline']),'original delivery envelope '+str(owner))
                if previous and previous['epoch']==r['epoch']:
                    margin=int(previous['deadline'])-int(r['ns'])
                    require(margin>0,'Leaf renewal after old expiry '+str(owner))
                    require(int(r['source'])>int(previous['source']),'nonfresh command '+str(owner))
                    minimum=margin if minimum is None else min(minimum,margin)
                    margins.append({'owner':owner,'epoch':r['epoch'],'source':r['source'],'received':r['ns'],'previous_expiry':previous['deadline'],'margin_ns':margin})
                previous=r
            require(seen==set(sent),'unreceived command '+str(owner))
            out['leaves'].append({'owner':owner,'sent':len(sent),'received':len(received),'minimum_margin_ns':minimum})
        out['minimum_margin_ns']=min((r['margin_ns'] for r in margins),default=None)
        with (folder/'renewal-margins.csv').open('w') as f:
            writer=csv.DictWriter(f,fieldnames=['owner','epoch','source','received','previous_expiry','margin_ns']);writer.writeheader();writer.writerows(margins)
    except (OSError,ValueError,KeyError) as e:require(False,'renewal evidence missing: '+str(e))
    return out
