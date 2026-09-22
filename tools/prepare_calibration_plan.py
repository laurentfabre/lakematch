#!/usr/bin/env python3
"""Freeze family metadata and explicit inputs; never open campaign source rows."""
import argparse
import hashlib
import json
from pathlib import Path

from lakematch.benchmark.company_pilot import GeneratorSpec, family_partitions, rank

ROOT = Path(__file__).resolve().parents[1]


def prepare():
    original = json.loads((ROOT/'bench/lakefusion/company-pilot-v0.1.json').read_text())
    partitions = family_partitions(GeneratorSpec(**original['spec']))
    ranked = sorted(partitions['development'], key=lambda f:rank(20260927,'lf-b-fit-calibration',f))
    families = {'fit':sorted(ranked[:4000]),'calibration':sorted(ranked[4000:]),
                'validation':sorted(partitions['validation'])}
    if any(set(families[a]) & set(families[b]) for a,b in [('fit','calibration'),('fit','validation'),('calibration','validation')]):
        raise ValueError('Overlapping families')
    paths = [ROOT/n for n in ['pyproject.toml','.python-version','requirements-local.lock',
        'tools/lakefusion_calibration.py','tools/prepare_calibration_plan.py','tools/experiment.py','tools/evidence.py',
        'tools/check_changes.py','tests/test_company_calibration.py','tests/conftest.py',
        'bench/lakefusion/CALIBRATION_PLAN.md','bench/lakefusion/company-pilot-v0.1.json',
        'spec/lakefusion/frozen/phase-a-v0.1.json','src/lakematch/benchmark/company_pilot.py',
        'src/lakematch/benchmark/company_calibration.py']]
    paths += list((ROOT/'src/lakematch/mastering').glob('*.py'))
    paths += [ROOT/'examples/mastering/company_pilot'/name for name in ['domain.json','erp_vendor_mapping.json','crm_account_mapping.json']]
    return {'schema_version':1,'phase':'LF-B','expected_prior_runs':10,'phase_limit':12,
        'source_manifest':'bench/lakefusion/company-pilot-v0.1.json',
        'source_directory':'data/lakefusion/company-pilot-v0.1',
        'artifact_directory':'data/lakefusion/calibration-v1',
        'family_selection_seed':20260927,'audit_seed':20260928,'bootstrap_seed':20260929,
        'bootstrap_repetitions':200,'families':families,'model_l2':.001,'calibration_l2':.0001,
        'clip_epsilon':1e-6,'precision_target':.995,
        'accept_grid':[.9,.95,.975,.99,.995,.999,1.],'reject_grid':[0.,.001,.005,.01,.025,.05,.1],
        'versions':{'numpy':'2.5.3','scipy':'1.18.1'},
        'files':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths))}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    target=ROOT/'bench/lakefusion/calibration-inputs-v1.json'
    expected=json.dumps(prepare(),indent=2)+'\n'
    if args.check:
        if target.read_text()!=expected: raise SystemExit('Calibration plan differs from source/metadata')
        print('Calibration plan matches pinned source and disjoint family metadata')
    else:
        with target.open('x') as stream: stream.write(expected)
        print(target.relative_to(ROOT))


if __name__=='__main__':
    main()
