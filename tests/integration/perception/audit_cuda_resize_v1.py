"""Audit the explicit GPU resize from both original inference-owner reports."""
import json


def validate(server, owner, renderer):
    declared = server.get('cuda_resize')
    if (not isinstance(declared, dict) or set(declared) != {'library', 'sha256'}
            or not declared['library'] or len(declared['sha256']) != 64):
        raise ValueError('explicit pinned CUDA resize declaration')
    if owner['preparation_thread_overrides'] != dict(cv=4, resize=0):
        raise ValueError('owner CUDA preparation thread settings')
    pipeline = renderer['host_pipeline']
    if pipeline['cv_threads'] != 4 or pipeline['resize_threads'] != 0:
        raise ValueError('renderer CUDA preparation thread settings')
    records = []
    for report, count in ((owner, len(owner['preparation_calls']) + len(owner['model_calls'])),
                          (renderer, len(renderer['preparation']) + len(renderer['inference']))):
        value = report.get('cuda_resize', {})
        if (value.get('kind') != 'cuda-two-pass-exact-v1'
                or any(value.get(k) != v for k, v in declared.items())
                or value.get('cpu_resize_threads') != 0
                or value.get('host_wait') != 'cudaEventBlockingSync'
                or value.get('calls') != count or count < 3
                or value.get('failures') != 0 or value.get('closed') is not True
                or type(value.get('owner_native_tid')) is not int or value['owner_native_tid'] <= 0):
            raise ValueError('complete successful GPU resize lifetime and library identity')
        records.append(value)
    if records[1]['owner_native_tid'] != pipeline['thread_id']:
        raise ValueError('renderer inference and CUDA ownership differ')
    owner_ids = {r['owner_thread_id'] for r in owner['preparation_calls'] + owner['model_calls']}
    if owner_ids != {records[0]['owner_thread_id']}:
        raise ValueError('owner inference and CUDA ownership differ')
    if any('error' in r for r in renderer['inference'] + owner['model_calls']):
        raise ValueError('no failed inference hidden by successful resize count')
    return dict(status='PASS_EXPLICIT_CUDA_RESIZE_ONLY', owner=records[0], renderer=records[1],
                native_perception_accepted=False)


def audit(run):
    read = lambda name: json.loads((run / name).read_text())
    return validate(read('server.json'), read('capture/perception.json'),
                    read('capture/paired/renderer/result.json'))
