"""Independent original owner-wire terminal StopLease / selected ACK decoder."""
from audit_m7_1q_native import check,wire


def stop_selection(proof,actuals,now,old_lease=None,causal=None):
    lease=None
    for role in range(3):
        zone=0 if role<2 else 1
        q=wire(proof['stop_requests'][role],zone,role+2,5)
        epoch,token,sent,deadline,op=q.get('IQQQI')
        kind=q.get('B');check(kind in (0,1,2,3),'stop request frame variant')
        q.get('IBBB');q.take(32 if kind<2 else 64)
        check(q.get('BBB')==(0,0,1),'exclusive original stop lease')
        current=q.get('IIQQ')
        check(q.pos==len(q.data),'complete stop request')
        a=wire(proof['stop_results'][role],role+2,zone,6)
        check(a.get('B')==1,'LeafResult variant')
        ae,at,source,operation,accepted=a.get('IQQIB')
        check(a.pos==len(a.data),'complete selection ACK')
        check(epoch==ae==current[0]==42 and token==at and op==operation==2 and accepted==1,'original accepted Stop selection')
        check(int(proof['enable_ns'])<=current[2]<=sent<=source<=actuals[role]['source']<=now and
              source<deadline<=current[3] and now+10000000<current[3]<=current[2]+80000000 and
              now+10000000-current[2]<=50000000,'Stop selection whole interval')
        check(lease is None or lease==current,'same three-leaf stop authority');lease=current
        check(actuals[role]['state']==0 and actuals[role]['origin']==1,'terminal NormalPath Init Actual')
        if causal is not None:check(actuals[role]['causal']==causal[role],'held original command causal')
    check(actuals[2]['value']==0 and actuals[2]['wheel']<=.01 and actuals[1]['value']>=100000,'stationary stop evidence')
    if old_lease:
        check(lease==old_lease or (0<lease[1]-old_lease[1]<=10 and lease[2]>old_lease[2]),'monotonic stop lease')
        check(now<old_lease[3] and now-old_lease[2]<=50000000,'no expired lease revival')
    return lease
