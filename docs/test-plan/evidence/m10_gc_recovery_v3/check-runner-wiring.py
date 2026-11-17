"""Check the actual launch precondition and paired live/frozen audit entrypoints."""
import ast
import hashlib
import json
from pathlib import Path
import os
import subprocess
import sys
import tempfile

SERIES=Path(__file__).resolve().parent
path=SERIES/'prospective-runner.py'
tree=ast.parse(path.read_text())
live=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='live')
conditions=[n.test for n in ast.walk(live) if isinstance(n,ast.Assert)
            and 'code-equivalence.json' in ast.unparse(n.test)]
assert len(conditions)==1
assert eval(compile(ast.Expression(conditions[0]),str(path),'eval'),
            {'json':json,'SERIES':SERIES}),'live precondition rejects actual equivalence report'
audit=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='audit_and_seal')
direct=[];frozen=[]
for node in ast.walk(audit):
    if not isinstance(node,ast.Call) or not isinstance(node.func,ast.Name):continue
    if node.func.id=='script' and isinstance(node.args[0],ast.Constant):
        direct.append(node.args[0].value)
    if node.func.id=='call':
        for value in ast.walk(node.args[0]):
            if isinstance(value,ast.Constant) and isinstance(value.value,str) and value.value.startswith('archive-check/source/'):
                frozen.append(Path(value.value).name)
for name in frozen:
    if name=='audit-workspace.py':continue # explicit series-local auditor in both paths
    assert direct.count(name)==frozen.count(name)==1,('live/frozen audit mismatch',name)
assert len(frozen)==8 and frozen.count('audit_library_prefetch_v1.py')==1
assert direct.count('audit_library_prefetch_v1.py')==1 and 'audit_owner_three_v1.py' not in direct
flags=[n.value for n in ast.walk(live) if isinstance(n,ast.Constant) and isinstance(n.value,str)]
assert flags.count('--owner-recovery-preview')==flags.count('--owner-purge-slice')==flags.count('--prefetch-inference-libraries')==1
root=SERIES.parents[3]
entrypoints=[root/'tests/integration/perception'/name for name in frozen if name!='audit-workspace.py']
entrypoints.append(SERIES/'audit-workspace.py')
with tempfile.TemporaryDirectory() as folder:
    env={k:v for k,v in os.environ.items() if k!='PYTHONPATH'}
    for entrypoint in entrypoints:
        completed=subprocess.run([sys.executable,str(entrypoint),'--help'],cwd=folder,
                                 env=env,capture_output=True,text=True,timeout=10)
        assert completed.returncode==0,(str(entrypoint),completed.stderr)
result=dict(status='PASS_LAUNCH_AND_REPRODUCTION_WIRING',runner_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            actual_equivalence_precondition=True,frozen_auditors=sorted(frozen),
            standalone_auditors_checked=len(entrypoints),live_processes_started=0,
            subprocesses_started=len(entrypoints),host_settings_changed=False)
(SERIES/'runner-wiring.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
