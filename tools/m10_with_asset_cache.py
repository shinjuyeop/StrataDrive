#!/usr/bin/env python3
"""Own temporary asset placement around the existing unattended finite trial."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import traceback
from m10_asset_cache import install,restore,load,validate_installed,identity,save

ROOT=Path(__file__).resolve().parents[1]


def main(series):
    declaration=json.loads((series/'cache-manifest.json').read_text())
    cache=Path(declaration['cache']);out=series/'cache-execution.json'
    if out.exists():raise ValueError('preserve the previous cache execution')
    plan=load(cache)
    if plan['entries']!=declaration['entries'] or plan['inventory_identity']!=declaration['inventory_identity']:
        raise ValueError('declared original asset identities and cache targets')
    report=dict(status='FAIL',declaration=identity(series/'cache-manifest.json'),scope=__doc__)
    installed=False;map_installed=False;map_declaration=None
    if (series/'map-config.json').exists():
        from m10_renderer_map import install as install_map,restore as restore_map
        map_declaration=json.loads((series/'map-config.json').read_text())
    try:
        report['installation']=install(cache);installed=True
        report['before']=validate_installed(cache)
        if report['before']['cache_device'] in report['before']['original_devices']:
            raise ValueError('separate NVMe filesystem required')
        if map_declaration:
            report['map_installation']=install_map(map_declaration);map_installed=True
        save(out,report)
        report['launcher_exit']=subprocess.run([sys.executable,str(ROOT/'tools/m10_start_owner_gc_unattended.py')],cwd=ROOT).returncode
        report['after']=validate_installed(cache)
        report['status']='PASS_STORAGE_PLACEMENT_ONLY'
    except BaseException as error:
        report['error']=traceback.format_exc()
        if isinstance(error,KeyboardInterrupt):report['interrupted']=True
    finally:
        if map_installed:
            try:report['map_restoration']=restore_map(map_declaration)
            except BaseException:report.update(status='FAIL',map_restoration_error=traceback.format_exc())
        if installed:
            try:report['restoration']=restore(cache)
            except BaseException:
                report.update(status='FAIL',restoration_error=traceback.format_exc())
        save(out,report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('before','after')}),flush=True)
    if report['status']!='PASS_STORAGE_PLACEMENT_ONLY':raise SystemExit(1)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--series',type=Path,required=True);main(p.parse_args().series.resolve())
