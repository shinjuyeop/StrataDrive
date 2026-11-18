from pathlib import Path
import subprocess,sys
p=Path(__file__).resolve();subprocess.run([sys.executable,str(p.parents[4]/'tools/m10_prepare_empty_pair.py'),'--series',str(p.parent)],check=True)
