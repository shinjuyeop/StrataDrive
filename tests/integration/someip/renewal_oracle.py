"""Offline actual-Leaf renewal checks; no timing/authority repair."""
import csv
from pathlib import Path


def renewal_oracle(folder,three=False,epoch=None,target=None):
    folder=Path(folder)
    out={'pass':True,'errors':[],'leaves':[]}
    def require(ok,why):
        if not ok:out['pass']=False;out['errors'].append(why)
    def read(name):
        with (folder/name).open() as f:return list(csv.DictReader(f))
    margins=[]
    try:
        central='central-1-rejoined' if epoch else 'central-1'
        central_rows=read(central+'.transport.csv')
        tx=[r for r in central_rows if r['event']=='central-enqueued' and int(r['operation'])==3]
        accepted={(int(r['epoch']),int(r['payload_source']),int(r['peer'])):r for r in central_rows if r['event']=='central-result-accepted' and int(r['operation'])==3}
        for owner,role,peer in [(2,'front',0),(3,'front',0),(4,'rear' if three else 'central',1)]:
            sent={(int(r['epoch']),int(r['payload_source'])):r for r in tx if int(r['peer'])==peer}
            prefix=role+('-2' if epoch and role==target else '-1')
            events=read(prefix+'.leaf-events.csv')
            remote_rows=read(prefix+'.transport.csv') if three else []
            zone_rx={(int(x['epoch']),int(x['token'])):x for x in remote_rows if x['event']=='zone-received' and int(x['operation'])==3}
            leaf_tx={(int(x['epoch']),int(x['token'])):x for x in remote_rows if x['event']=='zone-leaf-enqueued' and int(x['peer'])==owner}
            received=[r for r in events if int(r['owner'])==owner and r['event']=='valid-input' and int(r['detail'])==1 and (epoch is None or int(r['epoch'])==epoch)]
            require(len(received)>=10 and len(received)==len(sent),'command count/missing Leaf '+str(owner))
            seen=set();previous=None;minimum=None
            for r in sorted(received,key=lambda r:int(r['ns'])):
                key=(int(r['epoch']),int(r['source']));request=sent.get(key)
                require(request is not None and key not in seen,'unknown/duplicate accepted Leaf command '+str(owner));seen.add(key)
                if request:
                    require(int(r['deadline'])==int(request['inner_deadline']),'changed original command expiry '+str(owner))
                    require(int(request['sent'])<=int(r['ns'])<int(request['deadline']),'original delivery envelope '+str(owner))
                    if three:
                        identity=(int(request['epoch']),int(request['token']));zr=zone_rx.get(identity);lr=leaf_tx.get(identity)
                        require(zr is not None and lr is not None,'missing token path '+str(owner))
                        if zr and lr:
                            require(all(zr[k]==request[k] for k in ('epoch','token','sent','deadline','inner_deadline','original_source','payload_source')),'Zone changed command/permission '+str(owner))
                            require(lr['payload_source']==r['source'] and int(request['ns'])<=int(zr['ns'])<=int(lr['ns'])<=int(r['ns']),'Leaf handoff time/order '+str(owner))
                        result=accepted.get((key[0],key[1],peer))
                        require(result is not None,'no corresponding accepted result '+str(owner))
                        if peer==1:
                            front=accepted.get((key[0],key[1],0))
                            require(front is not None and int(front['ns'])<=int(request['sent']),'Rear sent before Front result')
                if previous and previous['epoch']==r['epoch']:
                    margin=int(previous['deadline'])-int(r['ns'])
                    require(margin>0,'Leaf renewal after old expiry '+str(owner))
                    require(int(r['source'])>int(previous['source']),'nonfresh command '+str(owner))
                    minimum=margin if minimum is None else min(minimum,margin)
                    margins.append({'owner':owner,'epoch':r['epoch'],'source':r['source'],'token':request.get('token','') if request else '', 'sent':request['sent'] if request else '', 'permission_source':request.get('original_source','') if request else '', 'expiry':r['deadline'],'zone_received':zone_rx.get((key[0],int(request['token'])),{}).get('ns','') if three and request else '', 'received':r['ns'],'previous_expiry':previous['deadline'],'margin_ns':margin})
                previous=r
            require(seen==set(sent),'unreceived command '+str(owner))
            out['leaves'].append({'owner':owner,'sent':len(sent),'received':len(received),'minimum_margin_ns':minimum})
        out['minimum_margin_ns']=min((r['margin_ns'] for r in margins),default=None)
        with (folder/'renewal-margins.csv').open('w') as f:
            writer=csv.DictWriter(f,fieldnames=['owner','epoch','source','token','sent','permission_source','expiry','zone_received','received','previous_expiry','margin_ns']);writer.writeheader();writer.writerows(margins)
    except (OSError,ValueError,KeyError) as e:require(False,'renewal evidence missing: '+str(e))
    return out
