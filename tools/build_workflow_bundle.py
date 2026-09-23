#!/usr/bin/env python3
"""Build an isolated Apps payload from explicit bindings; never deploy or provision."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

import yaml

from evidence import ROOT, sha256

sys.path.insert(0, str(ROOT/'runtime/src'))
from lakematch_runtime.settings import Binding


def build(output, binding_path, warehouse_id, review_schema):
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Choose a fresh output directory')
    binding = Binding.load(binding_path)
    if (not re.fullmatch(r'[a-zA-Z0-9-]{1,64}', warehouse_id)
            or not re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*', review_schema)):
        raise ValueError('Explicit review warehouse ID and catalog.schema required')
    app = output/'app'
    app.mkdir(parents=True)
    subprocess.run([sys.executable, str(ROOT/'app/build_deploy.py')], cwd=ROOT/'app',
                   check=True, timeout=420)
    for project in ('app', 'runtime'):
        subprocess.run(['uv', 'build', str(ROOT/project), '--wheel', '--no-create-gitignore', '--out-dir', str(app/'wheels')],
                       cwd=ROOT, check=True, timeout=90)
    wheels = sorted((app/'wheels').glob('*.whl'))
    if len(wheels) != 2:
        raise ValueError('Expected one app wheel and one workflow wheel')
    exported = subprocess.check_output(['uv', 'export', '--project', str(ROOT/'app'), '--frozen',
        '--no-dev', '--no-emit-project', '--format', 'requirements-txt'], cwd=ROOT, text=True, timeout=60)
    (app/'dependencies-app.txt').write_text(exported)
    shutil.copyfile(ROOT/'requirements-postgres.lock', app/'dependencies-postgres.txt')
    shutil.copyfile(ROOT/'runtime/requirements-yaml.lock', app/'dependencies-yaml.txt')
    (app/'requirements.txt').write_text('--require-hashes\n-r dependencies-app.txt\n-r dependencies-postgres.txt\n'
        '-r dependencies-yaml.txt\n'+''.join('./wheels/'+p.name+' --hash=sha256:'+sha256(p)+'\n' for p in wheels))
    shutil.copyfile(binding_path, app/'binding.json')
    config = {'command': ['python', '-m', 'lakematch_runtime'], 'env': [
        {'name': 'LAKEMATCH_WORKFLOW_BINDING', 'value': 'binding.json'},
        {'name': 'LAKEMATCH_REVIEW_STORE', 'value': 'delta'},
        {'name': 'LAKEMATCH_REVIEW_WAREHOUSE_ID', 'valueFrom': 'sql-warehouse'},
        {'name': 'LAKEMATCH_REVIEW_SCHEMA_NAME', 'value': review_schema},
        {'name': 'LAKEMATCH_REVIEW_GENIE_ENABLED', 'value': 'false'}]}
    (app/'app.yaml').write_text(yaml.safe_dump(config, sort_keys=False))
    bundle_config = {'command': config['command'], 'env': [
        {('value_from' if k == 'valueFrom' else k): v for k, v in entry.items()} for entry in config['env']]}
    bundle = {'bundle': {'name': 'lakematch-workflow-'+binding.app_name,
                         'deployment': {'lock': {'enabled': True}}},
        'sync': {'include': ['app/**']},
        'resources': {'apps': {'workflow': {'name': binding.app_name,
            'description': 'Lakematch governed workflow pilot', 'source_code_path': './app',
            'compute_size': 'MEDIUM', 'compute_min_instances': 1, 'compute_max_instances': 1,
            'lifecycle': {'started': False},
            'config': bundle_config, 'resources': [
                {'name': 'postgres', 'postgres': {'branch': binding.endpoint.split('/endpoints/')[0],
                    'database': binding.database_resource, 'permission': 'CAN_CONNECT_AND_CREATE'}},
                {'name': 'sql-warehouse', 'sql_warehouse': {'id': warehouse_id, 'permission': 'CAN_USE'}}]}}},
        'targets': {'pilot': {'mode': 'development', 'presets': {'name_prefix': ''},
            'workspace': {'host': binding.workspace_host,
                'root_path': '/Workspace/Users/${workspace.current_user.userName}/.bundle/lakematch-workflow/'+binding.app_name}}}}
    (output/'databricks.yml').write_text(yaml.safe_dump(bundle, sort_keys=False))
    paths = [p for p in output.rglob('*') if p.is_file() and p.name != '.gitignore']
    if any(p.stat().st_size >= 10*1024**2 for p in paths) or sum(p.stat().st_size for p in paths) >= 100*1024**2:
        raise ValueError('Apps payload exceeds the declared file or aggregate size limit')
    report = {'schema_version': 1, 'status': 'built; deployment not performed',
        'binding_sha256': sha256(binding_path), 'app_name': binding.app_name,
        'python': ['3.11', '3.12'], 'files': {str(p.relative_to(output)): {'sha256': sha256(p), 'bytes': p.stat().st_size} for p in paths}}
    (output/'payload.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--binding', required=True, type=Path)
    parser.add_argument('--warehouse-id', required=True)
    parser.add_argument('--review-schema', required=True)
    args = parser.parse_args()
    report = build(args.output, args.binding, args.warehouse_id, args.review_schema)
    print(json.dumps({'status': report['status'], 'files': len(report['files']),
                      'bytes': sum(v['bytes'] for v in report['files'].values())}), flush=True)


if __name__ == '__main__':
    main()
