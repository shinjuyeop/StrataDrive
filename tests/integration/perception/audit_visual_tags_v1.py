"""Check owner-only visual proxy omission and the unchanged physical gates."""
import argparse
import json
from pathlib import Path
from audit_owner_four_v1 import audit as owner_four


def audit(run):
    result = owner_four(run)
    server = json.loads((run/'server.json').read_text())
    owner, renderer = (server['argv'][k] for k in ('owner', 'renderer'))
    flag = '-StrataM10NoVisualTags'
    if (server.get('owner_no_visual_tags') is not True or owner.count(flag) != 1
            or flag in renderer or '-nullrhi' not in owner or '-norenderthread' not in owner):
        raise ValueError('explicit NullRHI-only visual proxy omission')
    message = 'StrataM10NoVisualTags: retain semantic stencils; omit auxiliary visual tag components'
    if message not in (run/'owner.log').read_text() or message in (run/'renderer.log').read_text():
        raise ValueError('actual owner activation and unchanged renderer required')
    result.update(status='PASS_OWNER_VISUAL_TAG_INTEGRITY',
        scope='owner-only auxiliary visual proxy omission; original timing/admission checks; not physical acceptance')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--run', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True); a = p.parse_args()
    try: result = audit(a.run)
    except Exception as error: result = dict(status='FAIL', error=str(error).replace(str(a.run), '<run>'))
    a.output.write_text(json.dumps(result, indent=2)+'\n')
    raise SystemExit(0 if result['status'] == 'PASS_OWNER_VISUAL_TAG_INTEGRITY' else 1)
