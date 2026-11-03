import json,subprocess
from pathlib import Path
root=Path.cwd();work=root/'build/m9-startup-work'
paths=['central/diagnostics/diagnostics.cpp','central/diagnostics/diagnostics_journal.cpp','central/diagnostics/startup_diagnostics.cpp','central/session/session_coordinator.cpp','interfaces/session/session_participant.cpp','simulation/runtime/m4_async_runtime.cpp','simulation/runtime/m4_owner_network.cpp','simulation/runtime/m4_result.cpp']
entries=json.loads((root/'build/m1-angle/compile_commands.json').read_text());subset=[next(e for e in entries if e['file']==str(root/p)) for p in paths]
(work/'compilation-subset.json').write_text(json.dumps(subset,indent=2)+'\n')
with (work/'clang-tidy.log').open('w') as f:c=subprocess.run(['clang-tidy','-p',str(root/'build/m1-angle'),'--warnings-as-errors=*',*paths],stdout=f,stderr=subprocess.STDOUT)
with (work/'cppcheck.log').open('w') as f:p=subprocess.run(['cppcheck','--project='+str(work/'compilation-subset.json'),'--enable=warning,performance,portability','--error-exitcode=1','--suppress=missingIncludeSystem'],stdout=f,stderr=subprocess.STDOUT)
(work/'static-result.json').write_text(json.dumps(dict(translation_units=paths,clang_tidy_exit=c.returncode,cppcheck_exit=p.returncode),indent=2)+'\n');raise SystemExit(c.returncode or p.returncode)
