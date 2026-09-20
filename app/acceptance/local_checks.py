import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
root=ROOT/'data/app-acceptance-v1'
commands=[['apx','dev','check'],['.venv/bin/python','-m','pytest','tests','-q','--junitxml='+str(root/'app-tests.xml')],['apx','build']]
for command in commands:
    subprocess.run(command,cwd=ROOT/'app',check=True,timeout=180)
files=[p for p in (ROOT/'app/.build').rglob('*') if p.is_file()]
assert files and max(p.stat().st_size for p in files)<10*1024*1024
report={'status':'passed','checks':commands,'file_limit_bytes':10*1024*1024,'largest_file_bytes':max(p.stat().st_size for p in files),'files':{str(p.relative_to(ROOT)):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files}}
(root/'build-report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
