"""SIM-2 golden references and production-plan checks; runs unchanged on classic and Connect.

Fixtures were computed once using maintained independent metric implementations. Their versions,
URLs and composition conventions are pinned in fixtures/sota_reference.json and its generator.
No optional oracle package is required to run these tests.
"""
import json
from pathlib import Path

import pytest
from pyspark.sql import functions as F

from conftest import make_cfg
from lakematch import config, entity, features
from lakematch.features import sota

REFERENCE = json.loads((Path(__file__).parent/'fixtures'/'sota_reference.json').read_text())
ROOT = Path(__file__).resolve().parent.parent
SHORTLIST = [m for m in json.loads((ROOT/'spec/research/sota_candidates.json').read_text())['measures'] if m['shortlisted']]


def _score(spark, family, builder):
    rows = REFERENCE['strings']
    df = spark.createDataFrame([(i,r['a'],r['b']) for i,r in enumerate(rows)], 'id int, a string, b string')
    got = df.select('id', builder('a','b').alias('score'), builder('b','a').alias('reverse')).collect()
    for r in got:
        assert r.score == pytest.approx(rows[r.id][family],abs=1e-12), rows[r.id]
        assert r.reverse == pytest.approx(r.score,abs=1e-12)
        assert r.score == -1.0 or 0 <= r.score <= 1


def _dp_reference(spark, family, builder, index):
    _score(spark,family,builder)
    df = spark.createDataFrame(REFERENCE['exhaustive_binary_dp'],'a string,b string,osa double,lcs double')
    assert all(r.got == pytest.approx(r.expected,abs=1e-12) for r in df.select(
        builder('a','b').alias('got'), F.col(index).alias('expected')).collect())


def test_sota_osa_reference(spark):
    _dp_reference(spark,'osa',sota.osa,'osa')


def test_sota_lcs_indel_reference(spark):
    _dp_reference(spark,'lcs_indel',sota.lcs_indel,'lcs')


def test_sota_token_sort_lev_reference(spark):
    def score(a,b):
        prepare = lambda c: sota.sorted_tokens(entity.tokens(F.col(c)))
        return sota.token_sort_lev(prepare(a),prepare(b))
    _score(spark,'token_sort_lev',score)


def test_sota_padded_bigram_dice_reference(spark):
    _score(spark,'padded_bigram_dice', lambda a,b:
           sota.padded_bigram_dice(sota.bigram_counts(F.col(a)),sota.bigram_counts(F.col(b))))


def test_sota_qgram_count_cosine_reference(spark):
    _score(spark,'qgram_count_cosine', lambda a,b:
           sota.qgram_count_cosine(sota.trigram_counts(F.col(a)),sota.trigram_counts(F.col(b))))


def _weighted(spark, family, builder):
    rows=REFERENCE[family]
    df=spark.createDataFrame([(i,r['a'],r['b']) for i,r in enumerate(rows)],
                             'id int,a map<string,double>,b map<string,double>')
    got=df.select('id',builder(F.col('a'),F.col('b')).alias('score'),
                  builder(F.col('b'),F.col('a')).alias('reverse')).collect()
    for r in got:
        assert r.score==pytest.approx(rows[r.id]['score'],abs=1e-12),rows[r.id]
        assert r.reverse==pytest.approx(r.score,abs=1e-12)


def test_sota_weighted_jaccard_reference(spark):
    _weighted(spark,'weighted_jaccard',sota.weighted_jaccard)


def test_sota_soft_tfidf_lev_reference(spark):
    _weighted(spark,'soft_tfidf_lev',lambda a,b:sota.soft_tfidf_lev(sota.weighted_tokens(a),sota.weighted_tokens(b),30))


def _only_extras(fields, extras=None, **options):
    return make_cfg(entity={'fields':fields},features={
        'extra_families':list(config.EXTRA_FAMILIES) if extras is None else extras,
        'exclude':[f for f in config.FAMILIES if f not in config.EXTRA_FAMILIES],
        'embeddings':{'provider':'none'},**options})


def _pairs(rt,cfg):
    # Includes code, multi-code, dates and numbers to enforce field applicability.
    fields=list(cfg.fields)
    left=rt.spark.createDataFrame([('l',*['red abcdef']*len(fields))],
                                   'rid string,'+','.join(f'{f} string' for f in fields))
    right=rt.spark.createDataFrame([('r',*['abcdef red']*len(fields)),('missing',*['']*len(fields))],left.schema)
    l,r=features.prepare_sides(entity.prepare(left,cfg,'rid'),entity.prepare(right,cfg,'rid'),cfg)
    l,r=rt.materialize(l,'sota_l'),rt.materialize(r,'sota_r')
    pre=lambda df,p:df.select([F.col(c).alias(p+c) for c in df.columns])
    return pre(l,'l_').crossJoin(pre(r,'r_'))


def test_sota_plan_is_builtin(rt,capsys):
    fields={t:{'type':t} for t in config.FIELD_TYPES}
    fields['multi_code']={'type':'code','multi':True}
    cfg=_only_extras(fields)
    out,cols=features.compare(_pairs(rt,cfg),cfg,candidates=False)
    expected={f'{m["prefix"]}_{f}' for m in SHORTLIST for f,s in fields.items() if s['type'] in m['field_types']}
    assert set(cols)==expected
    assert {features.family_of(c) for c in cols}==set(config.EXTRA_FAMILIES)
    out.select(*cols).explain(True)
    plan=capsys.readouterr().out
    assert plan and not any(n.lower() in plan.lower() for n in
                           ('PythonUDF','BatchEvalPython','ArrowEvalPython','ScalaUDF','Invoke'))
    rows={r.r_id:r.asDict() for r in out.select('r_id',*cols).collect()}
    assert all(rows['missing'][c]==-1.0 for c in cols)
    assert all(0<=rows['r'][c]<=1 for c in cols)
    assert rows['r']['tsl_title']==1.0
    assert rows['r']['wja_title']==1.0
    assert rows['r']['stl_title']==pytest.approx(1.0)


def test_sota_registration_and_opt_in():
    assert set(config.EXTRA_FAMILIES)=={m['family'] for m in SHORTLIST}
    assert not set(config.EXTRA_FAMILIES)&features.active_families(config.build())
    for m in SHORTLIST:
        assert features.FAMILY_OF_PREFIX[m['prefix']]==m['family']
        cfg=config.build({'features':{'extra_families':[m['family']]}})
        assert m['family'] in features.active_families(cfg)
        cfg=config.build({'features':{'extra_families':[m['family']],'exclude':[m['family']]}})
        assert m['family'] not in features.active_families(cfg)


@pytest.mark.parametrize('value',['osa',None,{},[1],[{}],['unknown'],['edit'],['osa','osa']])
def test_sota_invalid_extra_families(value):
    with pytest.raises(config.ConfigError,match='extra_families'):
        config.build({'features':{'extra_families':value}})


@pytest.mark.parametrize('key',['token_cap','sota_max_chars'])
@pytest.mark.parametrize('value',[0,-1,True,1.5,'30',None])
def test_sota_invalid_limit(key,value):
    with pytest.raises(config.ConfigError,match=key):
        config.build({'features':{key:value}})


@pytest.mark.parametrize('builder',[sota.osa,sota.lcs_indel],ids=['osa','lcs_indel'])
def test_sota_explicit_character_limit(spark,builder):
    df=spark.createDataFrame([('abcd','abce')],'a string,b string')
    assert 0<=df.select(builder('a','b',4)).first()[0]<=1
    with pytest.raises(Exception,match='sota_max_chars'):
        df.select(builder('a','b',3)).collect()


def test_sota_soft_tfidf_lev_explicit_token_limit(spark):
    df=spark.createDataFrame([({'a':1.,'b':2.},{'a':1.})],'a map<string,double>,b map<string,double>')
    with pytest.raises(Exception,match='token_cap'):
        df.select(sota.soft_tfidf_lev(sota.weighted_tokens(F.col('a')),sota.weighted_tokens(F.col('b')),1)).collect()


def test_sota_exclusion_avoids_preparation(rt):
    cfg=_only_extras({'title':{'type':'title'}},exclude=list(config.FAMILIES))
    df=entity.prepare(rt.spark.createDataFrame([('1','test title')],'rid string,title string'),cfg,'rid')
    a,b=features.prepare_sides(df,df,cfg)
    assert a.columns==df.columns and b.columns==df.columns
