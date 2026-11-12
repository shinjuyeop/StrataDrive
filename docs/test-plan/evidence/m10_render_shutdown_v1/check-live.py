#!/usr/bin/env python3
"""Verify retained renderer evidence with frozen source; never start CARLA."""
import argparse
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import tarfile
import zlib


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value); return value


def extract(bundle, name, work):
    manifest = json.loads((bundle/name).read_text()); archive = bundle/manifest['archive']
    assert archive.stat().st_size == manifest['bytes'] and sha(archive) == manifest['sha256']
    with tarfile.open(archive) as tar:
        members = tar.getmembers()
        assert len(members) == len(manifest['members']) and {m.name for m in members} == set(manifest['members'])
        for member in members:
            path = Path(member.name)
            assert member.isfile() and not path.is_absolute() and '..' not in path.parts
            data = tar.extractfile(member).read(); item = manifest['members'][member.name]
            assert len(data) == item['bytes'] and hashlib.sha256(data).hexdigest() == item['sha256']
            target = work/path; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--work', type=Path, required=True); args = parser.parse_args()
    work = args.work.resolve(); work.mkdir(parents=True, exist_ok=False)
    bundle = Path(__file__).resolve().parent
    if (bundle/'evidence-manifest.json').exists():
        for name, item in json.loads((bundle/'evidence-manifest.json').read_text())['files'].items():
            path = bundle/name; assert path.stat().st_size == item['bytes'] and sha(path) == item['sha256'], name
    source, frozen = module('source_check', bundle/'check-evidence.py').extract(bundle, work)
    sys.path[:0] = [str(source), str(source/'tests/integration/perception')]
    from carla_render_replay_v1 import original_scenes
    from physical_ai.perception.carla_render_adapter_v1 import transform
    from physical_ai.perception.scene_mailbox_v1 import encode
    import carla
    import numpy as np
    from PIL import Image
    sdk_hashes = [value for name, value in frozen['external'].items() if name.endswith('/libcarla.cpython-310-x86_64-linux-gnu.so')]
    assert sdk_hashes == [sha(Path(carla.libcarla.__file__))]
    case = json.loads((bundle/'case.json').read_text())
    run = work/case['run']; run.mkdir()
    extract(bundle, 'run-manifest.json', run)
    if (bundle/'raw-manifest.json').exists(): extract(bundle, 'raw-manifest.json', run)
    original_bundle = bundle.parent/'m10_owner_split_v2'
    context, binding, scenes = original_scenes(original_bundle)
    by_frame = {s.frame:s for s in scenes}
    server = json.loads((run/'server.json').read_text())
    report = json.loads((run/'capture/result.json').read_text())
    baseline = json.loads((source/'docs/test-plan/evidence/m10_fence_compare_v1/build-02/manifest.json').read_text())
    restoration = json.loads((bundle/'restoration.json').read_text())
    for name, item in baseline['installed'].items():
        assert restoration[name]['sha256'] == frozen['external'][item['path']] == item['original_sha256']
    assert server['freeze_sha256'] == sha(bundle/'sources.json') == case['freeze_sha256']
    assert server['original_ini_sha256'] == server['restored_ini_sha256'] == restoration['settings']['sha256']

    def check(r, s):
        assert not r['live_physical_owner'] and not r['complete_scene']
        assert r['native_publications'] == r['inference_calls'] == 0
        assert not r['errors'] and not r['cleanup_errors'] and s['attempts'] == 1
        assert r['original'] == context and r['scene_packets'] == [encode(x).hex() for x in scenes]
        assert s['status'] == 'EXECUTED_REQUIRES_AUDIT'
        if case['overall_attempt_index'] == 1:
            assert r['status'] == 'FAIL' and 'Spawn failed because of collision at spawn position' in r['error']
            assert not r['raw'] and not r['mapped'] and not r['ticks']
            assert s['client_exit'] == 1 and s['server_exit'] == 130 and not s.get('forced_stop')
            return 0.
        assert r['status'] == 'PASS_RENDERER_DIAGNOSTIC_ONLY'
        assert s['client_exit'] == 0 and s['server_exit'] == case['expected_server_exit']
        assert bool(s.get('forced_stop')) == case['expected_forced_stop']
        shutdown = s['shutdown']
        assert shutdown['diagnostics_enabled'] and shutdown['limit_seconds'] == 30 and shutdown['diagnostic_after_seconds'] == 10
        assert shutdown['server_exit'] == s['server_exit'] and 'diagnostic' not in shutdown
        assert 0 < shutdown['end_wall_ns']-shutdown['begin_wall_ns'] < 10_000_000_000
        assert not (run/'shutdown').exists(), 'no debugger was attached in this clean case'
        if case['quiescent_cleanup']:
            assert s['quiescent_shutdown'] and '--quiescent-shutdown' in s['client_argv']
            held = r['quiescent_cleanup']; last = r['ticks'][-1]
            assert held['world'] == r['render_context']['world'] and held['frame'] == last['renderer_frame']
            assert held['source_ns'] == last['renderer_source_ns'] and held['frame_unchanged']
            assert held['synchronous_mode'] and held['fixed_delta_seconds'] == .05
            assert max(x['received_wall_ns'] for x in r['raw']) <= held['begin_wall_ns'] < held['end_wall_ns'] <= shutdown['begin_wall_ns']
            session = r['renderer_session']
            assert session['instance'] == r['renderer_instance'] and session['world'] == held['world']
            assert type(session['camera_id']) is int and session['camera_id'] > 0
            assert session['calibration_sha256'] == hashlib.sha256(json.dumps(r['calibration'],sort_keys=True).encode()).hexdigest()
        else:
            assert 'quiescent_cleanup' not in r
        assert r['clone_preparation'] == dict(spawn_point_index=0, source_pose_unchanged=True, physics_disabled_before_source_pose=True)
        attrs = r['calibration']['attributes']
        assert float(attrs['image_size_x']) == 2560 and float(attrs['image_size_y']) == 1536
        assert float(attrs['fov']) == 90 and float(attrs['sensor_tick']) == .05
        assert r['render_context']['step_seconds'] == .05
        assert all(x['state'] == 'Red' and x['frozen'] for x in r['render_context']['traffic_lights'])
        assert len(r['raw']) == 19 and len(r['ticks']) == len(r['mapped']) == 12
        raw = {x['frame']:x for x in r['raw']}; ticks = {x['renderer_frame']:x for x in r['ticks']}
        assert len(raw) == 19 and len(ticks) == 12 and len({x['renderer_frame'] for x in r['mapped']}) == 12
        assert {x['physical_frame'] for x in r['mapped']} == set(by_frame)
        previous = None; max_error = 0.
        for tick in r['ticks']:
            scene = by_frame[tick['physical_frame']]
            assert tick['scene_sha256'] == hashlib.sha256(encode(scene)).hexdigest()
            assert scene.acquired_end_ns <= tick['apply_begin_ns'] <= tick['apply_end_ns'] <= tick['tick_begin_ns'] <= tick['tick_end_ns']
            if previous:
                assert tick['renderer_frame'] == previous['renderer_frame']+1
                assert abs(tick['renderer_source_ns']-previous['renderer_source_ns']-50_000_000) <= 1000
                assert previous['tick_end_ns'] <= tick['tick_begin_ns']
            previous = tick
            assert tick['actual_pose_readback'] and len(tick['clone_readback']) == len(scene.actors)
            for pose, actual in zip(scene.actors, tick['clone_readback']):
                assert actual['source_actor_id'] == pose.actor_id and actual['clone_actor_id'] > 0
                matrix = actual['actual_transform_matrix']; expected = transform(carla, pose).get_matrix()
                assert len(matrix) == 4 and all(len(row) == 4 for row in matrix)
                assert all(math.isfinite(v) for row in matrix for v in row)
                error = max(abs(a-b) for ar, er in zip(matrix, expected) for a,b in zip(ar,er))
                assert error <= 1e-4; max_error = max(max_error,error)
        for item in r['mapped']:
            packet = raw[item['renderer_frame']]; tick = ticks[item['renderer_frame']]; scene = by_frame[item['physical_frame']]
            state = next(x for x in context['original_state_observations'] if x['frame'] == scene.frame)
            assert item['physical_frame'] == tick['physical_frame'] and item['physical_source_ns'] == scene.source_ns
            assert item['renderer_source_ns'] == packet['source_ns'] == tick['renderer_source_ns']
            assert item['scene_sha256'] == tick['scene_sha256']
            assert item['original_acquisition_begin_ns'] == scene.acquired_begin_ns
            assert item['original_state_received_wall_ns'] == state['begin_wall_ns']
            assert item['callback_received_wall_ns'] == packet['received_wall_ns'] >= tick['tick_begin_ns']
            assert packet['received_wall_ns']-scene.acquired_begin_ns >= 100_000_000
            assert item['unavailable_reason'] == 'original_scene_expired'
        return max_error
    error = check(report, server)
    images = []
    for row in report['raw']:
        path = run/'capture'/row['path']
        assert path.parent == run/'capture' and path.stat().st_size == row['stored_bytes'] and sha(path) == row['stored_sha256']
        decoder = zlib.decompressobj(); raw = decoder.decompress(path.read_bytes(), 2560*1536*4+1)
        assert decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail
        assert row['width'] == 2560 and row['height'] == 1536 and len(raw) == row['raw_bytes'] == 2560*1536*4
        assert hashlib.sha256(raw).hexdigest() == row['bgra_sha256']
        im = Image.frombytes('RGB',(2560,1536),raw,'raw','BGRX'); gray = np.asarray(im.convert('L'))
        std = float(gray.std()); black = float(np.mean(gray <= 5)); white = float(np.mean(gray >= 250))
        assert std >= 2 and black < .98 and white < .98
        images.append(dict(frame=row['frame'], rgb_sha256=hashlib.sha256(im.tobytes()).hexdigest(),
                           luma_std=std, near_black_fraction=black, near_white_fraction=white))
    rejected = []
    if case['overall_attempt_index'] >= 3:
        def reject(name, edit):
            r,s = copy.deepcopy(report),copy.deepcopy(server); edit(r,s)
            try: check(r,s)
            except (AssertionError, ValueError, KeyError, TypeError): rejected.append(name)
            else: raise AssertionError('mutation accepted: '+name)
        reject('complete-scene-promotion',lambda r,s:r.update(complete_scene=True))
        reject('control-publication',lambda r,s:r.update(native_publications=1))
        reject('lifecycle-relabel',lambda r,s:s.update(forced_stop=True,server_exit=-9))
        reject('shutdown-budget-change',lambda r,s:s['shutdown'].update(limit_seconds=60))
        reject('diagnostics-disabled',lambda r,s:s['shutdown'].update(diagnostics_enabled=False))
        if case['quiescent_cleanup']:
            reject('quiescent-frame-change',lambda r,s:r['quiescent_cleanup'].update(frame=r['quiescent_cleanup']['frame']+1))
            reject('quiescent-time-regression',lambda r,s:r['quiescent_cleanup'].update(end_wall_ns=1))
            reject('camera-calibration-change',lambda r,s:r['renderer_session'].update(calibration_sha256='00'*32))
        reject('physical-source-renewal',lambda r,s:r['mapped'][0].update(physical_source_ns=r['mapped'][0]['renderer_source_ns']))
        reject('acquisition-renewal',lambda r,s:r['mapped'][0].update(original_acquisition_begin_ns=r['mapped'][0]['callback_received_wall_ns']))
        reject('state-receipt-renewal',lambda r,s:r['mapped'][0].update(original_state_received_wall_ns=r['mapped'][0]['callback_received_wall_ns']))
        reject('renderer-source-mismatch',lambda r,s:r['mapped'][0].update(renderer_source_ns=1))
        reject('late-scene-promotion',lambda r,s:r['mapped'][0].update(unavailable_reason='available'))
        reject('missing-image',lambda r,s:r['raw'].pop())
        reject('clone-pose-drift',lambda r,s:r['ticks'][0]['clone_readback'][0]['actual_transform_matrix'][0].__setitem__(3,0.))
    result = dict(status='PASS_EVIDENCE_INTEGRITY_ONLY', live_trial_verdict=case['verdict'],
                  raw_images=len(images), mapped_images=len(report['mapped']), maximum_matrix_error=error,
                  rejected_mutations=rejected, images=images, complete_scene=False, concurrent_physics=False,
                  camera_identity_scope=('persisted renderer instance/world/camera/calibration' if case['quiescent_cleanup'] else 'single callback binding in frozen runner; sensor numeric ID not persisted'),
                  old_hang_explained=False, debugger_attached=False,
                  shutdown_seconds=(server['shutdown']['end_wall_ns']-server['shutdown']['begin_wall_ns'])/1e9,
                  quiescent_seconds=((report['quiescent_cleanup']['end_wall_ns']-report['quiescent_cleanup']['begin_wall_ns'])/1e9 if case['quiescent_cleanup'] else None),
                  accepted_perception_results=0)
    exclusion = json.loads((bundle/'future-exclusion.json').read_text())
    prior_path = bundle/exclusion['prior']; prior = json.loads(prior_path.read_text())
    assert sha(prior_path) == exclusion['prior_sha256'] and exclusion['prior_count'] == prior['count'] and prior['count'] >= 8997
    expected_hashes = sorted(set(prior['rgb_sha256']) | {x['rgb_sha256'] for x in images})
    assert exclusion['rgb_sha256'] == expected_hashes and exclusion['count'] == len(expected_hashes)
    assert exclusion['new_raw_packets'] == len(images) and exclusion['holdout_access'] is False
    (work/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'images'},indent=2))


if __name__ == '__main__': main()
