#!/usr/bin/env python3
"""SDK-free integrity, native physical service and preserved fail-closed audit."""
import hashlib
import json
from pathlib import Path
import runpy
import sys
import tarfile
import tempfile
sys.dont_write_bytecode=True
root=Path(__file__).resolve().parent
for line in (root/'SHA256SUMS').read_text().splitlines():
    expected,name=line.split('  ',1)
    if hashlib.sha256((root/name).read_bytes()).hexdigest()!=expected:raise ValueError('checksum mismatch: '+name)
sys.path.insert(0,str(root/'sources/tests/integration/diagnostics'))
service=runpy.run_path(str(root/'sources/tests/integration/diagnostics/audit_native_service.py'))
legacy={k:runpy.run_path(str(root/'sources/tests/integration/diagnostics'/n)) for k,n in [('routing','audit_native_routing.py'),('adoption','audit_native_adoption.py'),('central','audit_central_restart.py')]}
results=json.loads((root/'results.json').read_text())
def extract(name,directory):
    with tarfile.open(root/name) as archive:
        for member in archive.getmembers():
            p=Path(member.name)
            if p.is_absolute() or '..' in p.parts or member.issym() or member.islnk():raise ValueError('unsafe archive')
        archive.extractall(directory)
    return Path(directory)/name.removesuffix('.tar.gz')
for mode,row in results['service_complete'].items():
    with tempfile.TemporaryDirectory(prefix='stratadrive-native-service-') as directory:
        source=extract(row['archive'],directory)/'central-rejoin-1'
        if row['exit']!=0:
            case=service['prefix'](source/'native-diagnostics/central/service-case')
            r=json.loads((source/'result.json').read_text())
            if r['pass'] or case['rows'] or (source/'service-ready.json').exists():raise ValueError('failed service precondition granted authority')
            if any(r['cleared']!='0' for r in service['csv_rows'](source/'native-diagnostics/central/records.csv')):raise ValueError('DTC cleared after failed precondition')
            print(mode,'FAIL preserved; service entries=0, no endpoint or clear');continue
        d=service['load'](source);report=service['judge'](d);report['mutations_rejected']=service['mutations'](d)
        if report!=row['report']:raise ValueError('service denominator mismatch')
        print(mode,json.dumps(report,sort_keys=True))
for mode,cohort in results['regression'].items():
    with tempfile.TemporaryDirectory(prefix='stratadrive-native-regression-') as directory:
        source=extract(cohort['archive'],directory);passed=0
        for row in json.loads((source/'results.json').read_text()):
            if row['exit']!=0 or row['audit_exit']!=0:print(mode,row['case'],'FAIL preserved');continue
            kind='central' if row['case']=='central-process-rejoin' else 'adoption' if row['case'].endswith('process-rejoin') else 'routing'
            name='central-rejoin-1' if kind=='central' else 'restart-live-1' if kind=='adoption' else 'normal-1' if row['case']=='normal' else 'command-loss-1'
            d=legacy[kind]['load'](source/row['case']/name);legacy[kind]['judge'](d);legacy[kind]['mutations'](d);passed+=1
        if passed!=cohort['passed']:raise ValueError('regression denominator mismatch')
        print(mode,'regression',passed,'/',cohort['total'])
