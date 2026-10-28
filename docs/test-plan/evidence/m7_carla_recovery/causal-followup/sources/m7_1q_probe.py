#!/usr/bin/env python3
"""Native Actual -> server admission -> NoDrive functional closed loop.

Only this adapter owns CARLA stage/advance. No synthetic command/Actual fixture,
no corrected-wheel fallback, no timestamp repair, no general driving acceptance.
"""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import select
import subprocess
import time
import traceback

import carla
from audit_m7_1r_work import validate as validate_work, f32
from m7_1k_server_probe import FIELDS
from m7_sensor_capture import Capture
from m7_1p_bridge import aligned_snapshot, require, DOMAIN, SOURCE


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--native', type=Path, required=True)
    p.add_argument('--model', type=Path, required=True)
    p.add_argument('--fault', choices=('none', 'credit', 'command', 'snapshot','work-missing','work-duplicate','ev-ack-missing','ev-ack-duplicate','ev-ack-energy','rgb-drop','protection'), default='none')
    p.add_argument('--ticks', type=int, default=400)
    p.add_argument('--solver-work', action='store_true')
    p.add_argument('--scenario', type=Path)
    p.add_argument('--cameras', action='store_true')
    a = p.parse_args()
    require(150 <= a.ticks <= 950, 'bounded functional horizon')
    require(a.fault!='rgb-drop' or a.cameras, 'RGB fault requires cameras')
    require(not a.scenario or a.solver_work, 'scenario requires settled work')
    require(a.fault!='protection' or (a.solver_work and a.ticks==400), 'protection case requires 400 settled intervals')
    a.output.mkdir(parents=True, exist_ok=False)
    report = dict(status='FAIL', normal_driving_enabled=False, interval_work_valid=False,
                  mode='native eight-role functional Actual connection', fault=a.fault, cases=[])
    if a.scenario:
        report['scenario'] = dict(path=str(a.scenario),sha256=hashlib.sha256(a.scenario.read_bytes()).hexdigest(),text=a.scenario.read_text())
    events = []
    client = carla.Client('127.0.0.1', 2200)
    client.set_timeout(10)
    world = original = actor = process = stderr = None
    capture = Capture(a.output,a.fault=='rgb-drop') if a.cameras else None
    bound = False
    session, run = '0', ''
    key = os.environ['STRATADRIVE_M7_OWNER_KEY']
    history = {}
    count = normal = empty = 0
    work_sum = [0.,0.,0.,0.]
    ineligible = []
    settlements = 0
    stopped_frame = None
    raw = (a.output/'trace.jsonl').open('w')

    def case(name, ok, **kw):
        report['cases'].append(dict(name=name, status='PASS' if ok else 'FAIL', **kw))
        require(ok, name)

    def rpc(op, record=True, **kw):
        req = dict(op=op, **kw)
        if op not in ('describe', 'bind'):
            req.update(session=session, run=run)
        req['owner_key'] = key
        result = json.loads(client.m7_nodrive(json.dumps(req)))
        if record:
            events.append(dict(request={k:v for k,v in req.items() if k != 'owner_key'}, response=result))
        return result

    try:
        report['client_version'] = client.get_client_version()
        report['server_version'] = client.get_server_version()
        case('version', report['client_version'] == report['server_version'] == '294096e-dirty')
        world = client.get_world()
        case('dedicated_world', world.get_map().name.endswith('/Town03_Opt') and not list(world.get_actors().filter('vehicle.*')))
        original = world.get_settings()
        report['original_settings'] = {k:getattr(original,k) for k in FIELDS}
        settings = world.get_settings()
        settings.synchronous_mode, settings.fixed_delta_seconds, settings.no_rendering_mode = True, .01, not a.cameras
        settings.substepping, settings.max_substep_delta_time, settings.max_substeps = True, .01, 10
        world.apply_settings(settings)
        world.tick()  # sole unbound initialization tick, before ego creation
        blueprint = world.get_blueprint_library().find('vehicle.lincoln.mkz_2020')
        blueprint.set_attribute('role_name', 'm7_native_actual_functional')
        spawn = world.get_map().get_spawn_points()[0]
        report['route_fixture'] = dict(map=world.get_map().name,spawn_index=0,seed=dict(engine_fixed_seed=0,traffic_randomness='none'),
            weather='ClearNoon',traffic=False,controller='fixed requests; no route following',
            spawn=dict(x=spawn.location.x,y=spawn.location.y,z=spawn.location.z,
                       roll=spawn.rotation.roll,pitch=spawn.rotation.pitch,yaw=spawn.rotation.yaw),
            opendrive_sha256=hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest())
        world.set_weather(carla.WeatherParameters.ClearNoon)
        actor = world.spawn_actor(blueprint, spawn)
        if capture: capture.attach(world,actor,carla)
        model_hash = hashlib.sha256(a.model.read_bytes()).hexdigest()
        binding = rpc('bind', actor=str(actor.id), application='42', model_sha256=model_hash)
        bound, session, run = binding['locked'], binding['session'], binding['run']
        report['binding'] = binding
        case('native_binding', binding['ok'] and binding['effort_profile'] == 'virtual-ev-v1-native-functional' and
             binding['model_sha256'] == model_hash and binding['application'] == '42' and binding['physics']['inputs_zero'])
        frame, end = int(binding['frame']), binding['simulation_seconds']
        ph = binding['physics']
        case('vehicle320_profile', ph['vehicle_substeps_low'] == ph['vehicle_substeps_high'] == 320)
        snapshot, delivery = aligned_snapshot(world.get_snapshot, frame)
        case('initial_clock', snapshot.timestamp.elapsed_seconds == end and
             math.floor(end*1e9+.5) == int(binding['logical_begin_ns']))
        stderr = (a.output/'native.stderr').open('w')
        process = subprocess.Popen([str(a.native.resolve()), '--native-solver-work' if a.solver_work else '--native-actual-export','1','42','7',str(actor.id)]+(['--scenario',str(a.scenario)] if a.scenario else []),
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr, text=True)
        receipt = None
        for i in range(a.ticks+int(a.solver_work)):
            record = dict(index=i, frame=frame, simulation_seconds=end, physics=ph,
                          wall_begin_ns=time.monotonic_ns())
            try:
                if a.fault == 'snapshot' and i == 200:
                    record['fault'] = 'withheld current snapshot; previous object and timestamp retained'
                    # Explicit local delivery fault; no extra tick or timestamp repair.
                    getter = lambda: previous_snapshot
                else:
                    getter = world.get_snapshot
                snapshot, delivery = aligned_snapshot(getter, frame)
                record['snapshot_delivery'] = delivery
                state=snapshot.find(actor.id)
                require(state is not None or i==0,'missing actor state after first physics tick')
                record['vehicle_state']=dict(frame=snapshot.frame,timestamp=snapshot.timestamp.elapsed_seconds,
                    source_identity='CARLA.ActorSnapshot',valid=state is not None)
                if state is not None:
                    transform=state.get_transform();velocity=state.get_velocity()
                    record['vehicle_state'].update(
                        position_ue_m=[transform.location.x,transform.location.y,transform.location.z],
                        rotation_ue_deg=[transform.rotation.roll,transform.rotation.pitch,transform.rotation.yaw],
                        velocity_ue_m_s=[velocity.x,velocity.y,velocity.z])
                require(snapshot.timestamp.elapsed_seconds == end, 'snapshot source timestamp')
                require(ph['generation'] == binding['physics']['generation'] and ph['nodrive'], 'generation')
                require(ph['vehicle_substeps_low'] == ph['vehicle_substeps_high'] == 320, 'profile')
                wheels = ph['wheels']
                require(len(wheels) == 4, 'wheel count')
                for j,w in enumerate(wheels):
                    require(w['index'] == j and w['bone'] == binding['physics']['wheels'][j]['bone'] and
                            w['solver_omega_source'] == SOURCE and math.isfinite(w['solver_omega_rad_s']), 'solver source')
                omega = [w['solver_omega_rad_s'] for w in wheels]
                ns = math.floor(end*1e9+.5)
                history[ns] = (omega[2]+omega[3])/2
                line = f'WHEEL 1 42 7 {DOMAIN} {frame} {end:.17g} 0.01 {actor.id} {frame} {ns} ' + ' '.join(f'{v:.17g}' for v in omega)
                record['native_input'] = line
                if a.solver_work and receipt:
                    work = receipt['solver_work']
                    means = [(s['after_rad_s'][2]+s['after_rad_s'][3])/2 for s in work['steps']]
                    solver_dt=f32(f32(.01)*f32(1/320)) if work['sleeping'] else work['steps'][0]['dt_s']
                    packet = (f"WORK {frame} {receipt['logical_begin_ns']} {ns} "
                              f"{solver_dt:.17g} "
                              f"{work['sleeping']} {len(means)} "+' '.join(f'{v:.17g}' for v in means))
                    if i==200 and a.fault=='work-missing': packet=packet.rsplit(' ',1)[0]
                    record['work_input']=packet
                    process.stdin.write(packet+'\n')
                    if i==200 and a.fault=='work-duplicate': process.stdin.write(packet+'\n')
                record['wall_native_begin_ns']=time.monotonic_ns()
                process.stdin.write(line+'\n');process.stdin.flush()
                require(bool(select.select([process.stdout],[],[],10)[0]), 'native reply timeout')
                native = json.loads(process.stdout.readline())
                record['native'] = native
                record['wall_native_end_ns']=time.monotonic_ns()
                if i==200 and a.fault in ('work-missing','work-duplicate'):
                    require(native['status']=='FAIL' and native['next_frame'] is None,'native work fail closed')
                    stopped_frame=frame
                    report['fault_observed']='native solver work rejected before further model jobs/tick'
                    break
                require(native['status'] == 'WHEEL_SHADOW_BARRIER' and native['admission']['ok'], 'native admission')
                require(native['now_ns'] == ns and native['next_frame'] == frame+1 and native['service_mask'] == 255, 'barrier identity')
                if a.solver_work and receipt:
                    settlement=native['settlement']
                    require(native['energy_basis']=='OBSERVED_SOLVER_WORK_SINGLE_EV' and native['carla_work_valid'] and
                            settlement['frame']==frame and settlement['end_ns']==ns and
                            math.isclose(settlement['total_mechanical_j'],sum(work_sum),rel_tol=1e-12,abs_tol=1e-12),'single EV complete-frame work settlement')
                    if not (i==200 and a.fault=='ev-ack-missing'):
                        ack=dict(ticket=receipt['ticket'],frame=str(frame),end_ns=str(ns),basis=native['energy_basis'],
                                 total_mechanical_j=settlement['total_mechanical_j'],balance_j=settlement['balance_j'])
                        if i==200 and a.fault=='ev-ack-energy': ack['total_mechanical_j']+=1
                        accepted=rpc('settle_work',record=False,**ack)
                        record['settlement_ack']=accepted
                        if accepted['ok']: settlements+=1
                        if i==200 and a.fault=='ev-ack-duplicate':
                            require(accepted['ok'],'first ack');accepted=rpc('settle_work',record=False,**ack)
                            record['duplicate_settlement_ack']=accepted
                        if i==200 and a.fault in ('ev-ack-duplicate','ev-ack-energy'):
                            require(not accepted['ok'] and accepted['latched'] and accepted['reason']=='ev_settlement_rejected','settlement rejection')
                            stopped_frame=frame;report['fault_observed']=accepted['reason'];break
                        require(accepted['ok'] and not accepted['awaiting_ev_settlement'],'settlement ack')
                    if i==a.ticks:
                        record['terminal_settlement']=True
                        report['final_settlement']=settlement
                        break
                for field in ('sensor_wheel','returned_wheel'):
                    value = native[field]
                    if value is None:
                        require(not native['armed_fixture'], 'missing armed wheel')
                    else:
                        require(value['source_ns'] in history and abs(value['rad_s']-history[value['source_ns']]) <= (0 if field=='sensor_wheel' else .005+1e-12), 'native source/value provenance')
                if capture and capture.snapshot()['errors']:
                    require(a.fault=='rgb-drop' and capture.snapshot()['dropped'], 'unexpected camera delivery gap')
                    stopped_frame=frame
                    report['fault_observed']='RGB missing frame; no reuse or timestamp rewrite; next tick blocked'
                    break
                proof = copy.deepcopy(native['native_export'])
                for k in ('service_mask','credit_mask','release_mask'):
                    proof[k] = str(native[k])
                if i == 200 and a.fault in ('credit','command'):
                    if a.fault == 'credit': proof['credit'][3] = None
                    else: proof['commands'][0] = None
                    record['fault'] = 'withheld original '+a.fault+' packet; no substitute'
                staged = rpc('stage_native', record=False, frame=str(frame+1), native=proof)
                record['staged'] = staged
                if not staged['ok']:
                    record['rejection'] = staged['reason']
                    require(i == 200 and a.fault in ('credit','command','ev-ack-missing') and staged['latched'], 'unexpected server rejection')
                    if a.fault=='ev-ack-missing': require(staged['reason']=='ev_settlement_required','missing settlement gate')
                    # Query, don't retry stage/advance after rejection.
                    report['fault_observed'] = staged['reason']
                    stopped_frame = frame
                    break
                require(int(staged['frame']) == frame, 'stage frame')
                if i == 150:
                    # A second unprivileged client tries both writer and tick paths
                    # while a real native Actual is staged but not applied.
                    foreign = carla.Client('127.0.0.1', 2200)
                    foreign.set_timeout(10)
                    blocked = foreign.apply_batch_sync([carla.command.ApplyVehicleControl(actor.id, carla.VehicleControl(throttle=1))], False)
                    case('foreign_batch_writer_denied', len(blocked)==1 and blocked[0].has_error() and
                         'M7 exclusive zero-probe owner' in blocked[0].error)
                    caught = None
                    try:
                        foreign.get_world().tick()
                    except RuntimeError as exc:
                        caught = str(exc)
                    case('foreign_tick_denied', caught is not None and 'M7 exclusive zero-probe owner' in caught and
                         rpc('describe')['frame']==str(frame), error=caught)
                if i==199 and a.fault=='protection':
                    # Submit while native and CARLA still share this frame,
                    # BEFORE physics advances. The next native subjob can then
                    # select protection causally within the following interval.
                    # Sending at i=200 would retroactively affect replayed jobs.
                    process.stdin.write('PROTECT\n');process.stdin.flush()
                    record['protection_request']=dict(kind='trusted local safety selection; no brake value',
                        source_ns=ns,frame=frame,wall_sent_ns=time.monotonic_ns())
                record['wall_advance_begin_ns']=time.monotonic_ns()
                queued = rpc('advance', record=False, ticket=staged['ticket'])
                require(queued['ok'], 'advance not accepted; never retry')
                deadline = time.monotonic()+10
                receipt = None
                while time.monotonic() < deadline:
                    reply = rpc('receipt', record=False)
                    require(not reply['latched'], 'postphysics latch')
                    if reply.get('receipt',{}).get('ticket') == staged['ticket']:
                        receipt = reply['receipt'];break
                    time.sleep(.001)
                require(receipt is not None, 'ambiguous advance; no retry')
                record['receipt'] = receipt
                record['wall_receipt_ns']=time.monotonic_ns()
                require(all(receipt[k] == binding[k] for k in ('run','session','actor','application','model_id','model_sha256','effort_profile')), 'receipt scope')
                require(receipt['clock_domain'] == 'm7-native-simulation-elapsed' and
                        receipt['source_identity'] == 'native-eight-role-CAN-P05-Actual; authenticated-local-owner', 'source identity')
                require(int(receipt['frame']) == frame+1 and receipt['simulation_begin_seconds'] == end and
                        abs(receipt['simulation_end_seconds']-end-.01)<1e-6, 'receipt interval')
                require(int(receipt['logical_begin_ns']) == ns and int(receipt['logical_end_ns']) == ns+10000000, 'whole interval')
                require(receipt['original_actual']['native'] == proof and receipt['inputs_cleared_after_physics'] and
                        receipt['interval_work_valid'] == a.solver_work and receipt['solver_substep_work_observed'] == a.solver_work, 'original actual/completion/work')
                if a.solver_work:
                    work = receipt['solver_work']
                    validate_work(record)
                    for j in range(4): work_sum[j] += work['motor_work_j'][j]
                    if not work['forward_energy_eligible']: ineligible.append(i)
                applied = receipt['original_actual']['admitted_actual']
                for k in ('angle_rad','torque_nm','pressure_pa','oldest_actuator_ns','oldest_dependency_ns','exclusive_expiry_ns','normal','protection'):
                    require(applied[k] == native['admission'][k], 'server/native admission disagreement '+k)
                require(applied['empty_init'] == native['admission']['empty'], 'INIT admission')
                for j,w in enumerate(receipt['physics']['wheels']):
                    require(abs(w['set_drive_nm']-(applied['torque_nm']/2 if j>=2 else 0)) <= 1e-5, 'Actual drive mapping')
                    require(abs(w['set_friction_nm']-applied['pressure_pa']*.001/4) <= 1e-5, 'Actual brake mapping')
                count += 1;normal += applied['normal'];empty += applied['empty_init']
                previous_snapshot = snapshot
                frame, end, ph = int(receipt['frame']), receipt['simulation_end_seconds'], receipt['physics']
                if i == 150:
                    replay = rpc('advance', ticket=staged['ticket'])
                    case('ticket_single_use', not replay['ok'] and int(replay['frame'])==frame)
                    before = rpc('describe')['frame'];time.sleep(.25)
                    case('wall_pause_no_tick_or_restamp', rpc('describe')['frame'] == before)
            except Exception:
                record['error'] = traceback.format_exc()
                raise
            finally:
                record['wall_end_ns']=time.monotonic_ns()
                raw.write(json.dumps(record,separators=(',',':'))+'\n');raw.flush()
        if a.fault == 'none':
            case('native_closed_loop_complete', count == a.ticks and normal>300 and empty==4)
            if a.solver_work: case('all_receipts_settled_once',settlements==count)
            case('forward_motion_observed', ph['body_forward_velocity_m_s']>0, final_m_s=ph['body_forward_velocity_m_s'])
            rejected = rpc('stage', frame=str(frame+1))
            case('native_profile_rejects_synthetic_stage', not rejected['ok'] and rejected['latched'] and
                 rejected['reason']=='native_actual_only' and rejected['frame']==str(frame))
            report['status'] = 'PASS_FUNCTIONAL_NATIVE_SOLVER_WORK' if a.solver_work else 'PASS_FUNCTIONAL_NATIVE_ACTUAL'
        elif a.fault=='protection':
            case('protection_continues_physics',count==a.ticks and normal>100 and normal<200 and empty==4)
            case('protection_actual_at_end',native['admission']['protection'] and not native['admission']['normal'] and
                 native['admission']['torque_nm']==0 and native['admission']['pressure_pa']>=1000000)
            case('all_protection_receipts_settled',settlements==count)
            report['final_body_forward_m_s']=ph['body_forward_velocity_m_s']
            report['final_signed_solver_wheels_rad_s']=[w['solver_omega_rad_s'] for w in ph['wheels']]
            report['status']='PASS_FUNCTIONAL_PROTECTION_ACTUAL'
        elif a.fault=='rgb-drop':
            case('rgb_drop_before_next_tick',stopped_frame is not None and rpc('describe')['frame']==str(stopped_frame))
            report['status']='PASS_EXPECTED_SENSOR_STOP'
        elif a.fault in ('credit','command','work-missing','work-duplicate','ev-ack-missing','ev-ack-duplicate','ev-ack-energy'):
            case('server_rejection_before_next_tick', stopped_frame is not None and rpc('describe')['frame']==str(stopped_frame))
            report['status'] = 'PASS_EXPECTED_SERVER_REJECTION'
        else:
            raise AssertionError('snapshot fault was not observed')
    except Exception:
        report['error'] = traceback.format_exc()
        if a.fault == 'snapshot' and count==200 and 'snapshot missing/skipped' in report['error']:
            report['status'] = 'PASS_EXPECTED_SNAPSHOT_STOP'
    finally:
        raw.close()
        if capture:
            try:
                time.sleep(.5)  # bounded drain, no tick and no restamping
                capture.stop()
            except Exception:
                report['sensor_cleanup_error']=traceback.format_exc();report['status']='FAIL'
            finally:
                (a.output/'sensors.json').write_text(json.dumps(capture.snapshot(),indent=2)+'\n')
        report.update(receipts=count, normal_intervals=normal, empty_init_intervals=empty)
        if a.solver_work:
            report.update(solver_work_observed_intervals=count, motor_work_j=work_sum,
                          forward_energy_ineligible_intervals=ineligible, ev_settlement_connected=True,settlements=settlements,
                          interval_work_valid=count>0)
        try:
            if bound:
                before = rpc('describe')['frame']
                paused = rpc('pause')
                time.sleep(.25)
                after = rpc('describe')
                case('containment_pause_clear_no_tick', paused['latched'] and after['frame']==before and after['physics']['inputs_zero'])
                retry = rpc('advance', ticket='0')
                case('latched_no_resume', not retry['ok'] and retry['frame']==before)
                reset = rpc('reset')
                case('reset_requires_new_init', reset['ok'] and reset['latched'] and reset['physics']['inputs_zero'])
                closed = rpc('close')
                case('ego_destroyed', closed['ok'] and not closed['locked'] and not closed['registry_actor_present'])
                bound, actor = False, None
            if capture: capture.destroy()
            if process:
                process.stdin.close()
                report['native_exit'] = process.wait(timeout=10)
                process.stdout.close()
                if report['status'].startswith('PASS'): case('native_expected_exit', report['native_exit']==(1 if a.fault in ('work-missing','work-duplicate') else 0))
            if world and original and not bound:
                if actor: actor.destroy()
                world.apply_settings(original)
                report['restored_settings'] = {k:getattr(world.get_settings(),k) for k in FIELDS}
                case('restored_settings_actors', report['original_settings']==report['restored_settings'] and not list(world.get_actors().filter('vehicle.*')))
        except Exception:
            report['cleanup_error'] = traceback.format_exc();report['status']='FAIL'
            if process and process.poll() is None:
                process.kill();process.wait(timeout=5);report['forced_native_stop']=True
        if stderr: stderr.close()
        (a.output/'events.json').write_text(json.dumps(events,indent=2)+'\n')
        (a.output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
    return 0 if report['status'].startswith('PASS') else 1


if __name__ == '__main__':
    raise SystemExit(main())
