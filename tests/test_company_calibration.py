"""Analytical/toy checks only; these never open the 40k campaign corpus."""
from dataclasses import replace
import json
import math
from pathlib import Path
import shutil

import pytest

from lakematch.benchmark.company_calibration import (family_audit, fit_logistic, proposed_bands,
    select_thresholds, workload_metrics)
from lakematch.benchmark.company_pilot import GeneratorSpec, family_partitions, rank, training_pairs
from lakematch.mastering.company_score import (FEATURE_ORDER, LinearProbabilityModel,
    feature_contract, normalize_features, pair_features)
from lakematch.mastering.contracts import ContractError, digest


def fields(**changes):
    return {**dict(legal_name='Société Alpha SAS', country='FR', registration_id='00-123',
                  address_line1='1 Rue Émile', city='Lyon', postal_code='00123'), **changes}


def score(i, *, label=1, p=.9999, family=None, **changes):
    f = i if family is None else family
    return {'pair_id': digest(['toy',i]), 'left_id': f'l{i}', 'right_id': f'r{i}',
            'left_family': f, 'right_family': f, 'label': label,
            'raw_probability': p, 'probability': p, 'vetoes': [], **changes}


def test_feature_allowlist_normalization_and_missing_values():
    a = fields()
    b = fields(legal_name='societe alpha', registration_id='00123', address_line1='1 rue emile')
    f = pair_features(a,b)
    assert len(f)==len(FEATURE_ORDER)==11 and f[:6]==(1.,)*6
    assert f[-2:]==(0.,0.)
    empty = pair_features(fields(registration_id=None, postal_code=None),fields(registration_id=None, postal_code=None))
    assert empty[2]==empty[5]==0 and empty[-2:]==(1.,0.)
    conflict=pair_features(a,fields(registration_id='123'))
    assert conflict[2]==0 and conflict[-1]==1 # leading zeros remain significant
    assert normalize_features(fields(legal_name='Αλφα'))['legal_name']=='αλφα'
    assert pair_features(a,b)==pair_features(b,a)


@pytest.mark.parametrize('change',[{'family':3},{'source_id':'crm'},{'company':8},{'record_id':'key'},
                                 {'legal_name': True},{'country':'x'*2049}])
def test_metadata_and_invalid_values_cannot_enter_features(change):
    with pytest.raises(ContractError): pair_features(fields(),fields(**change))


def test_model_json_parity_saturation_and_binding():
    model=LinearProbabilityModel((0.,)*11,math.log(3),digest(feature_contract()))
    vector=pair_features(fields(),fields())
    assert model.probability(vector)==pytest.approx(.75)
    assert LinearProbabilityModel.from_dict(json.loads(json.dumps(model.definition())))==model
    assert replace(model,intercept=1000).probability(vector)==1
    assert replace(model,intercept=-1000).probability(vector)==0
    with pytest.raises(ContractError,match='implementation'): replace(model,feature_sha256='0'*64)
    for bad in [math.nan,math.inf,True,1001.]:
        with pytest.raises(ContractError): replace(model,intercept=bad)
    with pytest.raises(ContractError): model.probability([0.]*10)
    with pytest.raises(ContractError): model.probability([math.nan]*11)


def test_fit_optimizer_has_correct_direction_and_matches_portable_math():
    from scipy.special import expit
    result=fit_logistic([[0.],[0.],[1.],[1.]],[0,0,1,1],l2=.01)
    assert result['coefficients'][0]>0
    assert expit(result['intercept'])<.1
    assert expit(result['intercept']+result['coefficients'][0])>.9
    # A reversed relationship cannot produce a decreasing Platt transform.
    result=fit_logistic([[-1.],[-1.],[1.],[1.]],[1,1,0,0],l2=.001,calibration=True)
    assert result['coefficients'][0]==0.
    assert expit(result['intercept'])==pytest.approx(.5)


@pytest.mark.parametrize('features,labels', [([[0.],[1.]],[1,1]), ([[0.],[math.nan]],[0,1]), ([[0.],[1.]],[0]),
                                           ([[0.],[1.]],[0,2])])
def test_invalid_fitting_populations_fail(features,labels):
    with pytest.raises(ValueError): fit_logistic(features,labels,l2=.001)


def test_conflict_and_both_sides_of_one_to_one_ambiguity_veto():
    rows=[score(0),score(1,left_id='l0'),score(2,right_id='r3'),score(3),
          score(4,vetoes=['identifier_conflict']),score(5,p=.01),score(6)]
    bands=proposed_bands(rows,.1,.99)
    assert [bands[r['pair_id']] for r in rows]==['review']*5+['reject','accept']
    assert set(proposed_bands(rows,0,None).values())=={'review'}


def test_audit_never_reuses_either_family_and_is_order_independent():
    rows=[score(0),score(1,right_family=0),score(2),score(3,left_family=2)]
    bands={r['pair_id']:'accept' for r in rows}
    first=family_audit(rows,bands,seed=7)
    assert first==family_audit(rows[::-1],bands,seed=7)
    assert first['decisions']==2
    assert first['errors']==0 and first['lower_95']<.995


def test_selection_corrects_for_grid_search_and_does_not_relax_target():
    grid=[.9,.95,.975,.99,.995,.999,1.]
    def select(rows): return select_thresholds(rows,accept_grid=grid,reject_grid=[0,.01,.1],audit_seed=9,precision_target=.995)
    too_few=select([score(i) for i in range(598)])
    assert too_few['selection_table'][0]['audit']['lower_95']>=.995
    assert too_few['accept_at_least'] is None # nominal bound is insufficient after selection
    enough=select([score(i) for i in range(1100)])
    assert enough['accept_at_least']==.9 and enough['reject_below']==.1
    assert enough['automatic_execution_enabled'] is False
    one_error=select([score(i,label=int(i!=0)) for i in range(1100)])
    assert one_error['accept_at_least'] is None
    positives=[score(0,p=.005)]
    assert select(positives)['reject_below']==0


def test_workload_counts_missing_candidates_false_rejects_and_review():
    truth=[{'erp_key':f'l{i}','crm_key':f'r{i}','family':i//2,'stratum':'toy'} for i in range(4)]
    rows=[score(0,family=0),score(1,p=.001,family=0),score(2,label=0,p=.2,right_id='r3',family=1)]
    bands=proposed_bands(rows,.01,.99)
    metrics=workload_metrics(rows,truth,bands,audit_seed=5,bootstrap_seed=6,bootstrap_repetitions=20)
    assert metrics['candidate_recall']==.5 and metrics['accepted_recall']==.25
    assert metrics['retrieval_misses']==2 and metrics['rejected_positives']==1
    assert metrics['review_anchors']==3 and metrics['review_pairs']==1
    assert metrics['accepted_pair_precision']==1
    assert metrics==workload_metrics(rows[::-1],truth[::-1],bands,audit_seed=5,bootstrap_seed=6,bootstrap_repetitions=20)
    with pytest.raises(ValueError,match='labels'): workload_metrics([{**rows[0],'label':0}],truth,bands,
        audit_seed=5,bootstrap_seed=6,bootstrap_repetitions=20)


def test_fit_calibration_families_and_negative_endpoints_remain_disjoint():
    spec=GeneratorSpec(families=250,generation_seed=41,split_seed=42,perturbation_seed=43,
                       key_seed=44,order_seed=45,negative_seed=46)
    parts=family_partitions(spec)
    ordered=sorted(parts['development'],key=lambda f:rank(47,'lf-b-fit-calibration',f))
    fit,cal=set(ordered[:100]),set(ordered[100:])
    assert fit.isdisjoint(cal|set(parts['validation'])|set(parts['confirmation']))
    truth=[{'company':2*f+m,'family':f,'erp_key':f'e{2*f+m}','crm_key':f'c{2*f+m}'} for f in sorted(fit) for m in (0,1)]
    pairs=training_pairs(spec,'development',truth)
    assert len(pairs)==1200 and sum(r['label'] for r in pairs)==200
    assert {int(r['crm_key'][1:])//2 for r in pairs}<=fit
    assert {int(r['erp_key'][1:])//2 for r in pairs}<=fit


def test_toy_mapping_retrieval_scoring_and_replay_are_bound(tmp_path,monkeypatch):
    from tools import lakefusion_calibration as evaluator
    from lakematch.benchmark.company_pilot import build_partition, preparation_manifest
    from lakematch.mastering.score_contract import ArtifactRef, ScoreContext, PlattCalibration
    from lakematch.mastering.probability import implementation_digest
    spec=GeneratorSpec(families=250,generation_seed=41,split_seed=42,perturbation_seed=43,
                       key_seed=44,order_seed=45,negative_seed=46)
    parts=family_partitions(spec)
    data=build_partition(spec,'validation')
    directory=tmp_path/'toy'
    directory.mkdir()
    for name,rows in {**data['sources'],'truth':data['truth']}.items():
        (directory/f'validation.{name}.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    fixture=tmp_path/'examples/mastering/company_pilot'
    fixture.mkdir(parents=True)
    for name in ['domain.json','erp_vendor_mapping.json','crm_account_mapping.json']:
        shutil.copyfile(Path(__file__).resolve().parents[1]/'examples/mastering/company_pilot'/name,fixture/name)
    monkeypatch.setattr(evaluator,'ROOT',tmp_path)
    config={'source_directory':'toy','families':{'fit':parts['development'][:100],
        'calibration':parts['development'][100:],'validation':parts['validation']},
        'audit_seed':51,'bootstrap_seed':52,'bootstrap_repetitions':20}
    comparison,execution=evaluator.bindings()
    population=evaluator.load_population(config,'validation',comparison.mappings)
    model=LinearProbabilityModel((0.,)*11,math.log(3),digest(feature_contract()))
    manifest=preparation_manifest(spec)
    context=ScoreContext('toy_context',1,ArtifactRef('toy_model',1,digest(model.definition())),'memory:toy',
        ArtifactRef('toy_features',1,digest(feature_contract())),FEATURE_ORDER,comparison.ruleset.sha256,
        execution.sha256,evaluator.partition(config,manifest,'fit'))
    calibration=PlattCalibration('toy_calibration',1,context.sha256,evaluator.partition(config,manifest,'calibration'),
        1.,0.,1e-6,implementation_digest())
    rows,receipt=evaluator.score_population(population,comparison,execution,model,calibration)
    assert rows and receipt['retained_pairs']==len(rows)
    assert all(r['raw_probability']==pytest.approx(.75) for r in rows)
    selected={'reject_below':0.,'accept_at_least':1.}
    first=evaluator.evaluate(rows,population[0],selected,config)
    detached=LinearProbabilityModel.from_dict(json.loads(json.dumps(model.definition())))
    repeated,receipt2=evaluator.score_population(population,comparison,execution,detached,calibration)
    assert rows==repeated and receipt==receipt2
    assert first==evaluator.evaluate(repeated,population[0],selected,config)
    config['families']['validation'].append(10000)
    with pytest.raises(ValueError,match='population'):
        evaluator.load_population(config,'validation',comparison.mappings)
