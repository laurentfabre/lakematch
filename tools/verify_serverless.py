"""Read-only ZR-6 acceptance over sealed remote runs and actual evidence gaps."""
from evidence import ROOT, sha256
from report_serverless import collect


def check():
    runs, errors, _ = collect()
    for kind, row in runs.items():
        if not row['audited']:
            continue
        report = row['report']
        fixture = kind.endswith('fixture')
        inference_modules = {'__init__', 'config', 'entity', 'features', 'feature_stats', 'similarity',
            'native_ml', 'murmur3', 'candidates', 'blocking', 'quality/__init__', 'quality/native',
            'quality/dqx', 'quality/rules', 'benchmark/metrics'}
        # Benchmark CLI/tools are not imported by deployed inference tasks.
        # Check every recorded engine source that can affect these tasks.
        for path, expected in report['sources'].items():
            used = (path.startswith('src/lakematch/') and path not in {
                'src/lakematch/cli.py', 'src/lakematch/benchmark/campaign.py'}) if fixture else (
                path in {'src/lakematch/' + name + '.py' for name in inference_modules})
            used |= path in ({'deployment/train_cluster_fixture.py', 'deployment/cluster_fixture.py',
                              'resources/serverless_fixture.job.yml', 'integration/check_remote_cluster.py'} if fixture else {
                              'deployment/prepare.py', 'deployment/audit.py', 'resources/serverless.pipeline.yml',
                              'resources/serverless.job.yml', 'integration/check_dqx.py'})
            used |= not fixture and path.startswith('deployment/pipeline/')
            if used and (not (ROOT / path).is_file() or sha256(ROOT / path) != expected):
                if not fixture and path == 'src/lakematch/config.py':
                    try:
                        from config_compatibility import validate
                        proof = validate(expected)
                        assert proof['serverless_input_manifest_sha256'] == report['input_manifest_sha256']
                        continue
                    except (AssertionError, KeyError, OSError, ValueError):
                        pass
                errors.append(f'{kind}: compatible-source refresh required for {path}')
        if report['bundle_sha256'] != sha256(ROOT / 'databricks.yml'):
            errors.append(f'{kind}: bundle configuration changed')
    # No metric/profile parser has established this capability yet. Do not
    # accept an enabled setting or a hand-written percentage as execution proof.
    errors.append('Measured per-stage Photon task time and executed fallback operator profiles are missing')
    errors.append('Campaign-attributed observed DBUs/cost remain unreconciled')
    if not (ROOT / 'bench/PHOTON.md').is_file():
        errors.append('Missing Photon report')
    return errors
