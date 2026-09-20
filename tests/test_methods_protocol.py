import importlib.util
from pathlib import Path
import sys


def load_methods():
    sys.path.insert(0, str(Path("tools").resolve()))
    spec = importlib.util.spec_from_file_location("method_protocol", "tools/run_methods.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cardinality_comparisons_use_only_training_validation_relationships():
    method = load_methods()
    pairs = [{"a_id": "a", "b_id": "b", "label": 1., "split": "train"},
             {"a_id": "a", "b_id": "c", "label": 1., "split": "confirmation"}]
    assert method.policies(pairs, False) == ["unrestricted", "many_to_one", "one_to_one"]
    pairs[1]["split"] = "valid"
    assert method.policies(pairs, False) == ["unrestricted"]
    pairs[1].update(a_id="c", b_id="b")
    assert method.policies(pairs, False) == ["unrestricted", "many_to_one"]
    assert method.policies(pairs, True) == ["one_to_one", "many_to_one", "unrestricted"]


def test_macro_weights_corpora_not_variants_and_excludes_diagnostic():
    spec = importlib.util.spec_from_file_location('method_report', 'tools/report_methods.py')
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(Path('tools').resolve()))
    spec.loader.exec_module(module)
    reports = {}
    for name in module.EXPECTED:
        scores = [('a','b',.9),('a','c',.1)]
        truth = [['a','b',1.,'a'],['a','c',0.,'a']]
        rows, predictions = [], {}
        for variant in ('levenshtein__gbt','levenshtein__logistic_regression'):
            failed = variant.endswith('logistic_regression') and name == 'bpid'
            rows.append({'variant':variant,'f1':0. if failed else 1.,'threshold':.5,
                'cardinality':'unrestricted','feature_seconds':1.,'train_seconds':1.,'score_seconds':1.})
            predictions[variant]={'scores':[('a','b',.1),('a','c',.1)] if failed else scores,'labels':truth}
        reports[name]=({'rows':rows},predictions)
    reports['febrl4-no_ssn_dob']=({'rows':[]},{})
    result=module.macro(reports)
    assert abs(result['levenshtein__gbt']['macro_f1']-1.) < 1e-12
    assert abs(result['levenshtein__logistic_regression']['macro_f1']-6/7) < 1e-12
    assert result['levenshtein__gbt']['paired_delta_vs_levenshtein_gbt_95ci']==[0.,0.]
    delta=result['levenshtein__logistic_regression']['paired_delta_vs_levenshtein_gbt_95ci']
    assert all(abs(x+1/7)<1e-12 for x in delta)
