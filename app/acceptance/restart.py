"""Stop/start APX itself and compare the durable HTTP snapshot exactly."""
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
root=ROOT/'data/app-acceptance-v1'
url='http://127.0.0.1:9034/api/training-labels'

def fetch():
    with urllib.request.urlopen(url, timeout=3) as r: return json.load(r)

before=fetch()
assert len(before['reviews'])==20
subprocess.run(['apx','dev','stop'],cwd=ROOT/'app',check=True,timeout=60)
env={**os.environ,'LAKEMATCH_REVIEW_DATABASE':str(root/'review-v4.sqlite')}
log=(root/'restart-apx.log').open('w')
child=None
try:
    child=subprocess.Popen(['apx','dev','start','--attached','--skip-credentials-validation','--timeout','60'],cwd=ROOT/'app',env=env,stdout=log,stderr=subprocess.STDOUT)
    deadline=time.monotonic()+90
    while time.monotonic()<deadline:
        try: after=fetch(); break
        except OSError:
            if child.poll() is not None: raise RuntimeError('APX exited before HTTP readiness')
            time.sleep(1)
    else: raise TimeoutError('APX did not restart in 90 seconds')
    assert before==after
    report={'status':'passed','process_restart':True,'exact_snapshot_preserved':True,'reviewed':20,'label_set_sha256':after['label_set_sha256']}
    (root/'restart-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
finally:
    subprocess.run(['apx','dev','stop'],cwd=ROOT/'app',check=True,timeout=60)
    if child is not None:
        try: child.wait(timeout=15)
        except subprocess.TimeoutExpired: child.terminate(); child.wait(timeout=10)
    log.close()
