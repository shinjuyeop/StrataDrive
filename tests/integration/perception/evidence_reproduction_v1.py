"""Compare relocated audit failures without discarding their original meaning."""
import copy
from pathlib import Path


def relocated_result(result, run):
    value = copy.deepcopy(result)
    if value.get('status') == 'FAIL' and isinstance(value.get('error'), str):
        # Only a quoted child of this exact run root can be relocated. A sibling
        # path, a different missing member, or any other result field still fails.
        prefix = str(Path(run).resolve()).rstrip('/') + '/'
        for quote in ("'", '"'):
            value['error'] = value['error'].replace(quote + prefix, quote + '<run>/')
    return value


def require_reproduction(original, reproduced, original_run, reproduced_run):
    if relocated_result(original, original_run) != relocated_result(reproduced, reproduced_run):
        raise ValueError('original audit result changed after relocation')
