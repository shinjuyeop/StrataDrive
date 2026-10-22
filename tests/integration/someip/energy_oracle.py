"""Independent offline work/chemical-energy accounting for energy-cycle-v1.
An intended protection is not substituted for successful normal cycle coverage.
"""
import csv
import json
import math
from pathlib import Path


def energy_oracle(folder,case,mode):
    out={'pass':False,'errors':[]}
    try:
        folder=Path(folder)
        with (folder/'energy.csv').open() as f:rows=list(csv.DictReader(f))
        if len(rows)<20:raise ValueError('missing interval energy trace')
        r=[{k:float(v) for k,v in x.items()} for x in rows]
        if not all(math.isfinite(v) for x in r for v in x.values()):raise ValueError('nonfinite energy ledger')
        if not all(x['input_ns']<=x['begin_ns']<x['end_ns'] and x['end_ns']-x['input_ns']<=30_000_000 for x in r):raise ValueError('energy acquisition/interval metadata')
        if not all(b['end_ns']>a['end_ns'] and b['sequence']>a['sequence'] for a,b in zip(r,r[1:])):raise ValueError('physical ledger sequence/time reset')
        if len({x['model_epoch'] for x in r})!=1:raise ValueError('physical model reset across ECU session')
        # Initial vehicle state in this Host fixture is zero speed. Recompute
        # using actual raw energies, not just the encoded C++ residual field.
        residuals=[x['battery_draw_j']-sum(x[k] for k in ('capacitor_delta_j','kinetic_j','friction_j','road_j','motor_loss_j','auxiliary_j','ohmic_j','circuit_loss_j')) for x in r]
        couplings=[x['electrical_mechanical_j']-x['motor_work_j'] for x in r]
        motion=[x['kinetic_j']-x['motor_work_j']+x['friction_j']+x['road_j'] for x in r]
        if max(map(abs,residuals))>.001 or max(map(abs,couplings))>1e-6 or max(map(abs,motion))>1e-5:raise ValueError('independent combined/motion/coupling energy residual')
        if not all(b[k]>=a[k]-1e-10 for a,b in zip(r,r[1:]) for k in ('friction_j','road_j','motor_loss_j','auxiliary_j','ohmic_j','circuit_loss_j','received_dc_j')):raise ValueError('loss/received energy counter reset')
        files=[folder/('central-1-rejoined.energy-feedback.csv' if case=='restart-live' else 'central-1.energy-feedback.csv')]
        if not files:raise ValueError('missing validated remote energy feedback')
        with files[-1].open() as f:feedback=[{k:float(v) for k,v in x.items()} for x in csv.DictReader(f)]
        if not feedback:raise ValueError('missing validated feedback samples')
        if not all(x['source_ns']<=x['ns'] for x in feedback):raise ValueError('future feedback source')
        complete=case in ('normal','restart-live')
        epoch=max(x['epoch'] for x in feedback)
        active=[x for x in r if x['epoch']==epoch]
        if not active:raise ValueError('no released physical samples in current ECU Epoch')
        if complete:
            prefix='central-1-rejoined' if case=='restart-live' else 'central-1'
            with (folder/(prefix+'.events.csv')).open() as f:events=list(csv.DictReader(f))
            if not {'accelerate','coast','brake','hold'}<=set(e['event'] for e in events):raise ValueError('normal scenario phase missing')
            charge=[x for x in feedback if x['charge_present']]
            cap=[x for x in feedback if x['cap_present']]
            if len(charge)<10 or len(cap)<10:raise ValueError('missing actual BMS/capability evidence')
            if mode=='no-charge':
                if any(x['charge_w']!=0 for x in charge) or any(x['capability_nm']!=0 for x in cap):raise ValueError('charge-zero not issued by real BMS/Drive')
                if any(x['torque_nm']<-1 for x in active):raise ValueError('negative actual torque under charge-zero')
            else:
                if not any(x['torque_nm']<-1 and x['pressure_pa']>1000 and x['wheel_speed_rad_s']>2 for x in active):raise ValueError('missing actual simultaneous regeneration/friction')
                recovered=sum(max(0.,a['motor_work_j']-b['motor_work_j']) for a,b in zip(active,active[1:]))
                received=active[-1]['received_dc_j']-active[0]['received_dc_j']
                if recovered<=1 or received<=1:raise ValueError('no measured mechanical recovery and battery DC receipt')
                # A fresh low-speed zero capability plus actual zero torque must
                # occur after the observed regen phase; no instant-ramp claim.
                low=[x for x in feedback if x['cap_present'] and x['wheel_speed_rad_s']<=2 and x['capability_nm']==0 and abs(x['torque_nm'])<=1]
                if not low or max(x['source_ns'] for x in low)<=min(x['end_ns'] for x in active if x['torque_nm']<-1):raise ValueError('low-speed regeneration termination missing')
            if max(x['friction_j'] for x in active)<=1:raise ValueError('no actual friction dissipation')
        out.update({'pass':True,'samples':len(r),'epoch':epoch,'max_combined_residual_j':max(map(abs,residuals)),'max_coupling_residual_j':max(map(abs,couplings)),'max_motion_residual_j':max(map(abs,motion)),'peak_speed_rad_s':max(x['wheel_speed_rad_s'] for x in r),'final':{k:r[-1][k] for k in ('kinetic_j','motor_work_j','friction_j','road_j','battery_draw_j','received_dc_j','motor_loss_j','circuit_loss_j','auxiliary_j','ohmic_j','capacitor_delta_j','soc')}})
    except (OSError,ValueError,KeyError,TypeError,StopIteration,IndexError) as e:out['errors'].append(str(e))
    return out
