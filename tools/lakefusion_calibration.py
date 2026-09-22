#!/usr/bin/env python3
"""One predeclared fit/calibration evaluation or a fitting-free frozen replay."""
import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

from lakematch.benchmark.company_calibration import fit_logistic, proposed_bands, select_thresholds, workload_metrics
from lakematch.benchmark.company_pilot import GeneratorSpec, training_pairs
from lakematch.mastering.company_score import FEATURE_ORDER, LinearProbabilityModel, feature_contract, pair_features
from lakematch.mastering.contracts import DomainContract, SourceMapping, digest
from lakematch.mastering.execution import ExecutionSpec, project_rows, retrieval_digest
from lakematch.mastering.match_contract import MatchBinding, MatchRuleset
from lakematch.mastering.match_evidence import compare_pair, implementation_digest as comparison_digest
from lakematch.mastering.probability import (DiagnosticPair, VETOES, apply_calibration, calibration_metrics,
    implementation_digest as probability_digest, preview_decision)
from lakematch.mastering.retrieval import Limits, retrieve
from lakematch.mastering.score_contract import (ArtifactRef, DataPartition, DecisionBands, PairScore,
    PlattCalibration, ProbabilityBinding, ScoreContext)
from lakematch.mastering.survivorship_contract import MappingPin

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def verify(config, config_path, mode):
    for path, expected in config['files'].items():
        if sha(ROOT/path) != expected:
            raise ValueError(f'Changed declared input: {path}')
    for path, expected in read(ROOT/'spec/lakefusion/frozen/phase-a-v0.1.json')['files'].items():
        if sha(ROOT/path) != expected:
            raise ValueError(f'Changed frozen input: {path}')
    for path in [*config['files'], str(config_path.relative_to(ROOT))]:
        committed = subprocess.check_output(['git', 'show', 'HEAD:'+path], cwd=ROOT)
        if hashlib.sha256(committed).hexdigest() != sha(ROOT/path):
            raise ValueError(f'Uncommitted experimental input: {path}')
    for package, expected in config['versions'].items():
        if version(package) != expected:
            raise ValueError(f'Changed numerical environment: {package}')
    runs = [json.loads(line) for line in (ROOT/'experiments/runs.jsonl').read_text().splitlines()]
    prior = sum(r['phase'] == 'LF-B' for r in runs)
    expected = config['expected_prior_runs'] + int(mode == 'replay')
    if prior != expected or prior >= 12:
        raise ValueError('LF-B ledger does not match the reserved slot')
    active = [read(p) for p in (ROOT/'experiments').glob('*/manifest.json')]
    if not any(r.get('status') == 'running' and r.get('process_group_id') == os.getpgrp() for r in active):
        raise ValueError('Run only through the bounded experiment runner')
    source = ROOT/config['source_directory']
    if list(source.glob('confirmation.*')):
        raise ValueError('Confirmation unexpectedly materialized')
    manifest = read(ROOT/config['source_manifest'])
    for name, info in manifest['files'].items():
        if sha(source/name) != info['sha256']:
            raise ValueError(f'Changed source snapshot: {name}')
    return manifest


def bindings():
    fixture = ROOT/'examples/mastering/company_pilot'
    domain = DomainContract.from_dict(read(fixture/'domain.json'))
    mappings = tuple(SourceMapping.from_dict(read(fixture/f'{s}_mapping.json'), domain)
                     for s in ('erp_vendor', 'crm_account'))
    rules = MatchRuleset('pilot_calibration_rules', 1, domain.domain_id, domain.version, domain.sha256,
        tuple(MappingPin(m.source_id, m.version, m.sha256) for m in mappings), comparison_digest())
    execution = ExecutionSpec('pilot_calibration_retrieval', 1, domain.domain_id, domain.version, domain.sha256,
        mappings[0].source_id, mappings[0].version, mappings[0].sha256,
        mappings[1].source_id, mappings[1].version, mappings[1].sha256,
        'identifier_name', retrieval_digest(), Limits(seconds=120))
    return MatchBinding(rules, domain, mappings), execution


def load_population(config, role, mappings):
    partition = 'validation' if role == 'validation' else 'development'
    directory = ROOT/config['source_directory']
    truth = [json.loads(x) for x in (directory/f'{partition}.truth.jsonl').read_text().splitlines()]
    families = set(config['families'][role])
    truth = [t for t in truth if t['family'] in families]
    if Counter(t['family'] for t in truth) != Counter({f: 2 for f in families}):
        raise ValueError('Actual family population differs from the committed selection')
    sources, snapshots = [], []
    for mapping, truth_key in zip(mappings, ('erp_key', 'crm_key')):
        keys = {t[truth_key] for t in truth}
        if len(keys) != len(truth):
            raise ValueError('Duplicate truth source keys')
        raw = [json.loads(x) for x in (directory/f'{partition}.{mapping.source_id}.jsonl').read_text().splitlines()]
        raw = [r for r in raw if r[mapping.source_key] in keys]
        projected = project_rows(mapping, raw)
        if {r['record_id'] for r in projected} != keys:
            raise ValueError('Actual source population differs from truth keys')
        sources.append({r['record_id']: r for r in projected})
        records = {}
        for r in raw:
            receipt = mapping.apply(r)
            records[receipt['source_key']] = {'source_id': mapping.source_id, 'source_key': receipt['source_key'],
                'version': 1, 'mapping_version': mapping.version, 'mapping_sha256': mapping.sha256,
                'deleted': False, 'values': receipt['payload']}
        snapshots.append(records)
    return truth, sources, snapshots


def partition(config, manifest, role):
    source = 'validation' if role == 'validation' else 'development'
    files = {p: v for p,v in manifest['files'].items() if p.startswith(source+'.') and 'training_pairs' not in p}
    return DataPartition(role, digest({'source_files': files, 'families': config['families'][role], 'role': role}),
                         tuple(sorted(str(f) for f in config['families'][role])),
                         'sampled_training_pairs' if role == 'fit' else 'complete_candidates')


def score_population(population, comparison, execution, model, calibration=None):
    truth, sources, snapshots = population
    by_left = {t['erp_key']: t for t in truth}
    by_right = {t['crm_key']: t for t in truth}
    result = retrieve([sources[0][k] for k in sorted(sources[0])],
                      [sources[1][k] for k in sorted(sources[1])],
                      execution.retrieval_alternative, execution.limits)
    if result['retained_pairs'] > 100_000:
        raise ValueError('Candidate population exceeds the declared diagnostic row envelope')
    scores = []
    for row in result['rows']:
        left = row['left_id']
        for c in sorted(row['candidates'], key=lambda c: c['right_id']):
            right = c['right_id']
            evidence = compare_pair(comparison, snapshots[0][left], snapshots[1][right], candidate_methods=c['methods'])
            if evidence['decision']['route'] == 'exclude':
                raise ValueError('Unexpected excluded record in the declared legal-company population')
            features = pair_features(sources[0][left]['features'], sources[1][right]['features'])
            p = model.probability(features)
            q = apply_calibration(calibration, p)['probability'] if calibration else p
            scores.append({'pair_id': evidence['pair_id'], 'left_id': left, 'right_id': right,
                'comparison_sha256': evidence['evidence_sha256'], 'features': list(features),
                'methods': c['methods'], 'raw_probability': p, 'probability': q,
                'vetoes': sorted(r['rule_id'] for r in evidence['rules'] if r['rule_id'] in VETOES),
                'left_family': by_left[left]['family'], 'right_family': by_right[right]['family'],
                'label': int(by_left[left]['crm_key'] == right)})
    receipt = {k: result[k] for k in ('alternative', 'retained_pairs', 'posting_visits')}
    receipt.update(candidate_sha256=digest({k:v for k,v in result.items() if k != 'wall_seconds'}),
                   truncated_anchors=sum(r['truncated'] for r in result['rows']),
                   cap_positive_losses=sum(by_left[r['left_id']]['crm_key'] in r['dropped_right_ids'] for r in result['rows']),
                   max_candidates=max(len(r['candidates']) for r in result['rows']),
                   max_pre_cap=max(r['pre_cap_count'] for r in result['rows']))
    return scores, receipt


def evaluate(scores, truth, selection, config):
    bands = proposed_bands(scores, selection['reject_below'], selection['accept_at_least'])
    metrics = workload_metrics(scores, truth, bands, audit_seed=config['audit_seed'],
        bootstrap_seed=config['bootstrap_seed'], bootstrap_repetitions=config['bootstrap_repetitions'])
    diagnostics = calibration_metrics([DiagnosticPair(r['pair_id'], r['label'], r['raw_probability'], r['probability']) for r in scores])
    return {'workload': metrics, 'calibration': diagnostics, 'bands_sha256': digest(bands),
            'scored_pairs_sha256': digest(scores)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--mode', choices=['fit', 'replay'], required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--replay-freeze')
    args = parser.parse_args()
    started = time.monotonic()
    config_path = (ROOT/args.config).resolve()
    config = read(config_path)
    report_path, artifact_path = ROOT/args.output, ROOT/args.model
    raw_path = ROOT/config['artifact_directory']/f'{args.mode}-validation-scores.json'
    if report_path.exists() or raw_path.exists() or (args.mode == 'fit' and artifact_path.exists()):
        raise ValueError('Use new evidence paths; do not overwrite earlier results')
    manifest = verify(config, config_path, args.mode)
    comparison, execution = bindings()
    report = {'schema_version': 1, 'phase': 'LF-B', 'package': 'LM-014', 'mode': args.mode,
              'slot': 11 if args.mode == 'fit' else 12, 'started_at': datetime.now(timezone.utc).isoformat(),
              'source_commit': subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
              'config_sha256': sha(config_path), 'versions': config['versions'],
              'confirmation_materialized': False, 'remote_operations': False, 'automatic_execution_enabled': False,
              'cost': 'local CPU only; no billed cloud operation', 'memory_limit_bytes': 4*1024**3,
              'memory_enforcement': 'measured process peak gate; outer process timeout 900 seconds'}
    if args.mode == 'fit':
        fitting = load_population(config, 'fit', comparison.mappings)
        pairs = training_pairs(GeneratorSpec(**manifest['spec']), 'development', fitting[0])
        if len(pairs) != 6*len(fitting[0]):
            raise ValueError('Incomplete fitting-pair population')
        features = [pair_features(fitting[1][0][r['erp_key']]['features'], fitting[1][1][r['crm_key']]['features']) for r in pairs]
        fitted = fit_logistic(features, [r['label'] for r in pairs], l2=config['model_l2'])
        model = LinearProbabilityModel(tuple(fitted['coefficients']), fitted['intercept'], digest(feature_contract()))
        # Independent implementations must agree before any validation result.
        import numpy as np
        from scipy.special import expit
        array_p = expit(np.asarray(features) @ np.asarray(model.coefficients) + model.intercept)
        parity = max(abs(model.probability(f)-float(p)) for f,p in zip(features,array_p))
        if parity > 1e-12:
            raise ValueError('Portable scoring differs from fitted numerical implementation')
        context = ScoreContext('pilot_score_context', 1, ArtifactRef('pilot_logistic', 1, digest(model.definition())),
            args.model, ArtifactRef('pilot_features', 1, digest(feature_contract())), FEATURE_ORDER,
            comparison.ruleset.sha256, execution.sha256, partition(config, manifest, 'fit'))
        calibration_population = load_population(config, 'calibration', comparison.mappings)
        calibration_scores, calibration_receipt = score_population(calibration_population, comparison, execution, model)
        epsilon = config['clip_epsilon']
        logits = [[math.log(min(1-epsilon,max(epsilon,r['raw_probability']))) -
                   math.log1p(-min(1-epsilon,max(epsilon,r['raw_probability'])))] for r in calibration_scores]
        calibrated = fit_logistic(logits, [r['label'] for r in calibration_scores], l2=config['calibration_l2'], calibration=True)
        calibration = PlattCalibration('pilot_platt', 1, context.sha256, partition(config,manifest,'calibration'),
            calibrated['coefficients'][0], calibrated['intercept'], epsilon, probability_digest())
        for r in calibration_scores:
            r['probability'] = apply_calibration(calibration,r['raw_probability'])['probability']
        report['fitting'] = {'pairs': len(pairs), 'positives': sum(r['label'] for r in pairs),
            'families': len(config['families']['fit']), 'pairs_sha256': digest(pairs),
            'optimizer': fitted, 'portable_probability_max_error': parity}
        report['calibration_population'] = {'retrieval': calibration_receipt, 'optimizer': calibrated,
            'diagnostics': calibration_metrics([DiagnosticPair(r['pair_id'],r['label'],r['raw_probability'],r['probability']) for r in calibration_scores])}
    else:
        if not args.replay_freeze:
            raise ValueError('A committed replay freeze is required')
        freeze_path = ROOT/args.replay_freeze
        frozen = read(freeze_path)
        if subprocess.check_output(['git','show','HEAD:'+args.replay_freeze]) != freeze_path.read_bytes():
            raise ValueError('Replay freeze is not committed')
        if sha(artifact_path) != frozen['model_sha256'] or sha(ROOT/frozen['report']) != frozen['report_sha256']:
            raise ValueError('Selected frozen evidence changed')
        artifact = read(artifact_path)
        if artifact['config_sha256'] != sha(config_path):
            raise ValueError('Model is bound to another experiment plan')
        model = LinearProbabilityModel.from_dict(artifact['model'])
        context = ScoreContext.from_dict(artifact['score_context'])
        calibration = PlattCalibration.from_dict(artifact['calibration'])
        selection = artifact['selection']
        if selection['accept_at_least'] is None:
            raise ValueError('No selected passing threshold is available for replay')
        report['replay_freeze_sha256'] = sha(freeze_path)
        report['fitting_performed'] = report['threshold_selection_performed'] = False
    validation_population = load_population(config, 'validation', comparison.mappings)
    if (context.model.sha256 != digest(model.definition()) or context.feature_contract.sha256 != digest(feature_contract())
            or context.feature_order != FEATURE_ORDER or context.ruleset_sha256 != comparison.ruleset.sha256
            or context.retrieval_execution_sha256 != execution.sha256
            or context.fitting != partition(config,manifest,'fit')
            or calibration.calibration != partition(config,manifest,'calibration')
            or calibration.score_context_sha256 != context.sha256):
        raise ValueError('Model, features or partition bindings differ from the executed plan')
    scores, receipt = score_population(validation_population, comparison, execution, model, calibration)
    if args.mode == 'fit':
        selection = select_thresholds(scores, accept_grid=config['accept_grid'], reject_grid=config['reject_grid'],
            audit_seed=config['audit_seed'], precision_target=config['precision_target'])
    report['selection'] = selection
    evaluation = evaluate(scores, validation_population[0], selection, config)
    report['validation'] = {'retrieval': receipt, **evaluation}
    report['validation_sha256'] = digest(report['validation'])
    if args.mode == 'replay':
        expected = read(ROOT/frozen['report'])
        if report['validation_sha256'] != expected['validation_sha256']:
            raise ValueError('Frozen validation does not replay exactly')
        report['exact_validation_replay'] = True
    band_contract = None
    if selection['accept_at_least'] is not None:
        band_contract = DecisionBands('pilot_bands', 1, calibration.sha256, partition(config,manifest,'validation'),
                                      selection['reject_below'], selection['accept_at_least'])
        binding = ProbabilityBinding(comparison, context, calibration, band_contract)
        if args.mode == 'replay' and digest(artifact['bands']) != digest(asdict(band_contract)):
            raise ValueError('Replay band contract differs from the frozen model artifact')
        samples, seen = [], set()
        for r in scores:
            key = ('veto' if r['vetoes'] else 'eligible', bool(r['label']))
            if key in seen: continue
            seen.add(key)
            ev = compare_pair(comparison, validation_population[2][0][r['left_id']],
                              validation_population[2][1][r['right_id']],candidate_methods=r['methods'])
            sample = preview_decision(binding,ev,PairScore(context.sha256,ev['evidence_sha256'],r['raw_probability']))
            if sample['transform']['probability'] != r['probability']:
                raise ValueError('Worker probability preview differs from evaluation')
            samples.append({'pair_id': r['pair_id'], 'label': r['label'], 'result': sample})
        report['worker_preview_samples'] = samples
    if args.mode == 'fit':
        write_new(artifact_path, {'schema_version': 1, 'config_sha256': sha(config_path),
            'model': model.definition(), 'features': feature_contract(), 'score_context': asdict(context),
            'calibration': asdict(calibration), 'bands': asdict(band_contract) if band_contract else None,
            'selection': selection, 'retrieval': asdict(execution), 'ruleset': asdict(comparison.ruleset),
            'authority': 'unapproved synthetic worker; no automatic execution'})
    write_new(raw_path,scores)
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak = peak if sys.platform == 'darwin' else peak*1024
    if peak > report['memory_limit_bytes']:
        raise ValueError('Measured memory exceeds declared envelope')
    verify(config,config_path,args.mode)
    report.update(status='completed', model_sha256=sha(artifact_path), raw_scores=str(raw_path.relative_to(ROOT)),
        raw_scores_sha256=sha(raw_path), process_peak_rss_bytes=peak, wall_seconds=time.monotonic()-started,
        validation_selection_gate_passed=selection['accept_at_least'] is not None and evaluation['workload']['candidate_recall'] >= .95,
        quality_qualified=False, confirmation_gate='not evaluated; untouched',
        cleanup='no child service, database or remote resource started',
        ended_at=datetime.now(timezone.utc).isoformat())
    write_new(report_path,report)
    print(json.dumps({k:report[k] for k in ('status','slot','validation_selection_gate_passed','wall_seconds','process_peak_rss_bytes')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
