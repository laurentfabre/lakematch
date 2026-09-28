"""Protocol checks independent of the costly four-corpus benchmark."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

spec = importlib.util.spec_from_file_location("simbeat", Path(__file__).parents[1] / "bench/simbeat.py")
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def rows(value):
    return {c: {"f1": value} for c in s.CORPORA}


def test_simbeat_greedy_uses_full_precision_and_stops_on_tie():
    fs = s.shortlist()[:2]
    opts = [s.variant([f]) for f in fs]
    data = {"levenshtein": rows(.8), opts[0]: rows(.80000001), opts[1]: rows(.8)}
    step = s.choose_round([], opts, data)
    assert step['accepted'] and step['best'] == opts[0]
    data[opts[0]] = rows(.8)
    assert not s.choose_round([], opts, data)['accepted']


def test_simbeat_linkage_counts_missed_candidates_and_keeps_unmatched_units():
    linkage = {'units': ['a','b','c','d'], 'truth': [['a','1'], ['c','3']]}
    pred = [{'l_id':'a','r_id':'1','label':1.,'p':.9}, {'l_id':'b','r_id':'1','label':0.,'p':.8},
            {'l_id':'b','r_id':'2','label':0.,'p':.7}]
    units, counts = s.counts_for(pred, .5, linkage)
    assert units == linkage['units']
    assert counts.tolist() == [[1,0,0],[0,0,0],[0,0,1],[0,0,0]]
    assert float(s.f1(counts.sum(axis=0))) == pytest.approx(2/3)


def test_simbeat_paired_interval_identical_models_is_zero():
    counts = np.array([[1,0,0],[0,1,0],[0,0,1],[0,0,0]])
    per = {}
    for c in s.CORPORA:
        r = {**s.metrics(list('abcd'), counts), 'counts_by_unit': counts.tolist()}
        per[c] = {'chosen':r, 'jaro_winkler':r}
    t = s.aggregate_test(per)
    assert t['delta_mean_f1'] == 0 and t['delta_ci95'] == [0,0]


def test_simbeat_verdict_uses_all_four_conditions():
    d = {'valid': {'chosen':rows(.85), 'jaro_winkler':rows(.84), 'levenshtein':rows(.85)},
         'test': {'chosen':{'mean_f1':.83}, 'jaro_winkler':{'mean_f1':.83}}}
    assert s.recompute_verdict(d)[0] == 'beaten'
    d['valid']['chosen']['abt_buy']['f1'] = .839
    assert s.recompute_verdict(d)[0] == 'not_beaten'


def test_simbeat_jw_and_lev_cover_identical_fields():
    cols = ['lev_title', 'jw_title', 'eq_title', 'osa_title']
    assert s.select_cols(cols, 'levenshtein') == ['lev_title','eq_title']
    assert s.select_cols(cols, 'jaro_winkler') == ['jw_title','eq_title']
    assert s.select_cols(cols, 'levenshtein + osa') == ['lev_title','eq_title','osa_title']
