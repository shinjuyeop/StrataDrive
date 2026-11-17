"""Check the actual launch precondition and paired live/frozen audit entrypoints."""
import ast
import hashlib
import json
from pathlib import Path

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
assert len(frozen)==8 and frozen.count('audit_gc_recovery_v1.py')==1
assert direct.count('audit_gc_recovery_v1.py')==1 and 'audit_owner_three_v1.py' not in direct
flags=[n.value for n in ast.walk(live) if isinstance(n,ast.Constant) and isinstance(n.value,str)]
assert flags.count('--owner-recovery-preview')==flags.count('--owner-purge-slice')==1
result=dict(status='PASS_LAUNCH_AND_REPRODUCTION_WIRING',runner_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            actual_equivalence_precondition=True,frozen_auditors=sorted(frozen),
            processes_started=0,host_settings_changed=False)
(SERIES/'runner-wiring.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
