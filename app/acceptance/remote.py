"""One owned APX/Delta experiment, with finite deadlines and explicit cleanup."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import signal
import subprocess
import sys
import time
from uuid import uuid4

import requests
import yaml
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'app/src'))
from lakematch_review.backend.store import DeltaStore, TABLE_DDL
from lakematch_review.backend.models import PairOut
from lifecycle import wait_provisioned, stop_when_ready


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--profile',required=True);parser.add_argument('--report',required=True);args=parser.parse_args()
    if args.profile!='fevm-gdpr2': raise ValueError('Only explicitly selected fevm-gdpr2 is authorized')
    root=ROOT/'data/app-acceptance-v1'
    destination=ROOT/args.report;destination.parent.mkdir(parents=True,exist_ok=True)
    app_name='lakematch-review-20260919'
    schema='gdpr2_catalog.lakematch_20260919'
    warehouse='ec3b6df6c1cabcd4'
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    workspace=f'/Workspace/Users/laurent.fabre@databricks.com/lakematch/20260919/app_{stamp}'
    report={'profile':args.profile,'app_name':app_name,'warehouse_id':warehouse,'schema':schema,'workspace':workspace,'started_at':stamp,'status':'running','observed_cost':None,'commands':[],'cleanup':{}}
    work_deadline=time.monotonic()+1800
    cleaning=False
    def check_budget():
        if not cleaning and time.monotonic()>=work_deadline:
            raise TimeoutError('App work deadline reached; reserve remaining time for cleanup')
    def save(): destination.write_text(json.dumps(report,indent=2)+'\n')
    def cli(*parts,payload=None,timeout=90):
        check_budget()
        command=['databricks',*parts,'--profile',args.profile,'--output','json']
        if payload is not None: command+=['--json',json.dumps(payload)]
        report['commands'].append(command);save()
        remaining=timeout if cleaning else max(1,min(timeout,work_deadline-time.monotonic()))
        r=subprocess.run(command,cwd=ROOT,text=True,capture_output=True,timeout=remaining)
        if r.returncode: raise RuntimeError(r.stderr.strip()[:2000])
        try: return json.loads(r.stdout) if r.stdout.strip() else {}
        except ValueError: return {'completed':True}
    def poll(label,get,good,bad=(),seconds=480):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            item,state=get();report[label]=item;save()
            print(f'{label}: {state}',flush=True)
            if state in good:return item
            if state in bad:raise RuntimeError(f'{label}: {state}')
            time.sleep(5)
        raise TimeoutError(f'{label} exceeded {seconds}s')
    def app_state():
        item=cli('apps','get',app_name);return item,item.get('compute_status',{}).get('state')
    def warehouse_state():
        item=cli('warehouses','get',warehouse);return item,item.get('state')
    w=WorkspaceClient(config=Config(profile=args.profile,http_timeout_seconds=55,retry_timeout_seconds=60))
    class BoundedStore(DeltaStore):
        def query(self, sql, params=None):
            check_budget()
            return super().query(sql, params)
    store=BoundedStore(w,warehouse,schema)
    owned=False;warehouse_started=False
    def interrupted(*_): raise KeyboardInterrupt('experiment interrupted')
    signal.signal(signal.SIGTERM,interrupted)
    save()
    try:
        active=cli('jobs','list-runs','--active-only')
        if isinstance(active,dict):active=active.get('runs',[])
        if any(r.get('run_name','').startswith('lakematch-') for r in active):raise RuntimeError('Another campaign experiment is active')
        apps=cli('apps','list')
        if isinstance(apps,dict):apps=apps.get('apps',[])
        existing=next((a for a in apps if a['name']==app_name),None)
        description='lakematch 20260919 campaign: synthetic APX review acceptance; stop after experiments'
        body={'name':app_name,'description':description,
              'forward_user_access_token':False,
              'resources':[{'name':'review-warehouse','sql_warehouse':{'id':warehouse,'permission':'CAN_USE'}}]}
        report['app_request']=body
        if existing:
            if existing.get('description')!=description:raise RuntimeError('App name belongs to another resource')
            owned=True
            if existing.get('compute_status',{}).get('state') not in {'STOPPED','IDLE'}:raise RuntimeError('Campaign app is already running')
        else:
            owned=True  # exact owned name; cleanup also handles a timed-out create response
            cli('apps','create','--no-compute','--no-wait',payload=body)
        app=report['created_app']=wait_provisioned(lambda:cli('apps','get',app_name));save()
        principal=app['service_principal_client_id']
        if not all(c in '0123456789abcdef-' for c in principal):raise ValueError('Unexpected app principal identifier')
        warehouse_started=True
        cli('warehouses','start',warehouse,'--no-wait')
        poll('warehouse_running',warehouse_state,{'RUNNING'},seconds=300)
        for name,ddl in TABLE_DDL.items():
            store.query(f'CREATE TABLE IF NOT EXISTS {store.table(name)} ({ddl}) USING DELTA')
        if int(store.query(f"SELECT COUNT(*) FROM {store.table('review_labels')}")[0][0]):
            raise RuntimeError('Preserve existing labels: use the resume audit instead of seeding over them')
        for pair in json.loads((root/'queue.json').read_text()):
            store.enqueue(PairOut.model_validate(pair))
        for key,value in json.loads((root/'metadata.json').read_text()).items():
            store.set_metadata(key,value)
        store.query(f'GRANT USE CATALOG ON CATALOG gdpr2_catalog TO `{principal}`')
        store.query(f'GRANT USE SCHEMA ON SCHEMA {schema} TO `{principal}`')
        for name in TABLE_DDL:
            privileges='SELECT, MODIFY' if name=='review_labels' else 'SELECT'
            store.query(f'GRANT {privileges} ON TABLE {store.table(name)} TO `{principal}`')
        build=ROOT/'app/.build'
        config=yaml.safe_load((build/'app.yml').read_text())
        config['env']=[{'name':'LAKEMATCH_REVIEW_STORE','value':'delta'},
                       {'name':'LAKEMATCH_REVIEW_WAREHOUSE_ID','valueFrom':'review-warehouse'},
                       {'name':'LAKEMATCH_REVIEW_SCHEMA_NAME','value':schema},
                       {'name':'LAKEMATCH_REVIEW_GENIE_ENABLED','value':'false'}]
        (build/'app.yml').write_text(yaml.safe_dump(config))
        files=[p for p in build.rglob('*') if p.is_file()]
        assert files and max(p.stat().st_size for p in files)<10*1024*1024
        report['build_files']={str(p.relative_to(build)):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files}
        cli('workspace','import-dir',str(build),workspace,'--overwrite')
        deployed=cli('apps','deploy',app_name,'--source-code-path',workspace,'--no-wait')
        deployment_id=deployed['deployment_id'];report['deployment_id']=deployment_id;save()
        def deployment_state():
            item=cli('apps','get-deployment',app_name,deployment_id)
            return item,item.get('status',{}).get('state')
        poll('deployment',deployment_state,{'SUCCEEDED'},{'FAILED','CANCELLED'},seconds=600)
        app=report['running_app']=cli('apps','get',app_name);url=app['url'].rstrip('/');save()
        def api(method,endpoint,body=None):
            check_budget()
            response=requests.request(method,url+'/api/'+endpoint,headers=w.config.authenticate(),json=body,timeout=max(1,min(120,work_deadline-time.monotonic())),allow_redirects=False)
            if response.status_code!=200:raise RuntimeError(f'App HTTP {response.status_code} at {endpoint}: {response.text[:500]}')
            return response.json()
        session=report['session']=api('GET','session');save()
        assert session['storage']=='delta' and session['user']!='local-reviewer'
        queue=api('GET','queue?limit=100')
        assert len(queue)==24
        ordered=sorted(queue,key=lambda p:(abs(p['probability']-p['threshold']),-p['impact'],p['pair_id']))
        assert queue==ordered
        reviews=[]
        for index,pair in enumerate(queue[:20]):
            decision='unsure' if index==19 else ('match' if pair['a_id'][1:]==pair['b_id'][1:] else 'no_match')
            body=dict(request_id=uuid4().hex,pair_id=pair['pair_id'],model_version=pair['model_version'],decision=decision,reason='Synthetic FEVM review: inspected the paired name and group.')
            saved=api('POST','reviews',body);reviews.append(saved)
            assert saved==api('POST','reviews',body)
            assert saved['user']==session['user'] and saved['reviewed_at'] and saved['reason']
            report['review_count']=len(reviews);save()
            print(f'Reviewed {len(reviews)}/20',flush=True)
        snapshot=api('GET','training-labels')
        assert len(snapshot['reviews'])==20 and len(snapshot['labels'])==19 and snapshot['excluded_unsure']==1
        assert store.snapshot().model_dump()==snapshot
        (root/'remote-http-snapshot.json').write_text(json.dumps(snapshot,indent=2)+'\n')
        report['snapshot']=snapshot;report['stats']=api('GET','statistics');save()
        cli('apps','stop',app_name,'--no-wait')
        poll('restart_stopped',app_state,{'STOPPED'},seconds=240)
        cli('apps','start',app_name,'--no-wait')
        poll('restart_started',app_state,{'ACTIVE'},{'ERROR','FAILED'},seconds=360)
        deadline=time.monotonic()+120
        while True:
            try: after=api('GET','training-labels');break
            except RuntimeError:
                if time.monotonic()>=deadline:raise
                time.sleep(5)
        assert after==snapshot
        report['restart_preserved_exact_snapshot']=True
        report['delta_independent_readback']=True
        report['status']='passed'
    except BaseException as exc:
        report['status']='failed';report['error']=f'{type(exc).__name__}: {exc}';save();raise
    finally:
        cleaning=True
        failures=[]
        if owned:
            try:
                stopped=stop_when_ready(lambda:cli('apps','get',app_name),
                                        lambda:cli('apps','stop',app_name,'--no-wait'),timeout=300)
                report['final_app']=stopped
                report['cleanup']['app']=stopped['compute_status']['state']
            except BaseException as exc:
                if 'does not exist or is deleted' in str(exc):
                    report['cleanup']['app']='not created; Apps API confirms absence'
                else:failures.append(f'app: {exc}')
        if warehouse_started:
            try:
                cli('warehouses','stop',warehouse)
                stopped=poll('final_warehouse',warehouse_state,{'STOPPED'},seconds=180)
                report['cleanup']['warehouse']=stopped['state']
            except BaseException as exc:failures.append(f'warehouse: {exc}')
        report['cleanup']['errors']=failures
        report['ended_at']=datetime.now(timezone.utc).isoformat();save()
        if failures:raise RuntimeError('Cleanup incomplete: '+'; '.join(failures))

if __name__=='__main__':main()
