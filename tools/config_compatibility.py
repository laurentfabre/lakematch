"""Prove that selected defaults do not alter fully specified remote inputs."""
import ast
from copy import deepcopy
import json
import sys
import types

from evidence import ROOT, sha256

BASELINE = '02cdf5b70a95956dfdc8b483b5ff87426a66347e2215157d767967e43df3a28f'
CHANGES = {
    ('candidates', 'method'): ('gram_topk', 'minhash_lsh'),
    ('features', 'multi_token'): ([], ['idf_token_cosine']),
    ('cluster', 'max_rounds'): (20, 30),
}


def without_defaults(source):
    tree = ast.parse(source)
    found = 0
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'DEFAULTS' for t in node.targets):
            node.value = ast.Constant(None)
            found += 1
    assert found == 1
    return ast.dump(tree)


def validate(expected_baseline=BASELINE):
    from lakematch.config import DEFAULTS, from_dict
    assert expected_baseline == BASELINE, 'Remote config is not the reviewed pre-default source'
    old_path = ROOT / 'data/config_sources' / (BASELINE + '.py')
    new_path = ROOT / 'src/lakematch/config.py'
    assert sha256(old_path) == BASELINE
    old_source, new_source = old_path.read_text(), new_path.read_text()
    assert without_defaults(old_source) == without_defaults(new_source), 'Config logic changed beyond defaults'
    module = types.ModuleType('_lakematch_config_before_defaults')
    sys.modules[module.__name__] = module
    try:
        exec(compile(old_source, str(old_path), 'exec'), module.__dict__)
        expected = deepcopy(module.DEFAULTS)
        for (section, key), (before, after) in CHANGES.items():
            assert expected[section][key] == before
            expected[section][key] = after
        assert DEFAULTS == expected, 'Unreviewed default change'
        configs = {name: entry['config'] for name, entry in json.loads((ROOT / 'bench/freeze.json').read_text())['models'].items()}
        for variant in ('all', 'no_ssn'):
            raw = json.loads((ROOT / 'data/serverless_frozen' / variant / 'config.json').read_text())
            for engine in ('native', 'dqx'):
                value = deepcopy(raw)
                value['quality']['engine'] = engine
                value['paid_features']['app'] = value['paid_features']['genie'] = engine == 'dqx'
                configs[f'serverless/{variant}/{engine}'] = value
        for name, raw in configs.items():
            assert module.from_dict(raw).data == from_dict(raw).data, f'Expanded configuration changed: {name}'
    finally:
        del sys.modules[module.__name__]
    return {'status': 'static_config_equivalence', 'baseline_source': str(old_path.relative_to(ROOT)),
        'baseline_sha256': BASELINE, 'current_source_sha256': sha256(new_path),
        'freeze_sha256': sha256(ROOT / 'bench/freeze.json'),
        'serverless_input_manifest_sha256': sha256(ROOT / 'data/serverless_frozen/manifest.json'),
        'equal_expanded_configs': sorted(configs),
        'scope': 'Only three selected defaults differ; all config logic and expanded frozen inputs are unchanged. '
                 'This does not substitute for measured prediction replay or newly defaulted configurations.'}


if __name__ == '__main__':
    print(json.dumps(validate(), indent=2))
