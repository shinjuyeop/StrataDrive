import datetime
import json
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent / 'validation'
name, *command = sys.argv[1:]
log = root / (name + '.txt')
metadata = root / (name + '.json')
if log.exists() or metadata.exists():
    raise SystemExit('Refusing to overwrite a validation attempt')
start = datetime.datetime.now(datetime.timezone.utc).isoformat()
with log.open('w') as out:
    run = subprocess.run(command, stdout=out, stderr=subprocess.STDOUT)
metadata.write_text(json.dumps(dict(argv=command, start_utc=start,
    end_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), returncode=run.returncode), indent=2)+'\n')
print(log.read_text()[-7000:])
print(f'{name}: exit {run.returncode}; log {log}')
raise SystemExit(run.returncode)
