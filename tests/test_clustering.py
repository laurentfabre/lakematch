import pytest

from lakematch.clustering import ConvergenceError, resolve
from lakematch.config import from_dict
from lakematch.runtime import Materializer, probe


def run(spark, method, max_rounds=20):
    config=from_dict({'entity':{'fields':{'name':{'type':'person_name'}}},
        'decision':{'threshold':.9},'cluster':{'method':method,'max_rounds':max_rounds}})
    vertices=spark.createDataFrame([('a',),('b',),('c',),('d',)],'rec_id string')
    edges=spark.createDataFrame([('a','b',.99),('b','c',.98)],'a_id string,b_id string,p double')
    evidence=spark.createDataFrame([('a','b',.99),('b','c',.98),('a','c',.1)],edges.schema)
    with Materializer(spark,config,probe(spark)) as materializer:
        result=resolve(vertices,edges,config,materializer,pair_scorer=lambda pairs:pairs.join(evidence,['a_id','b_id'],'left'))
        groups={}
        for row in result.membership.collect(): groups.setdefault(row.cluster,set()).add(row.rec_id)
        tables=[event['table'] for event in materializer.events]
    assert not any(spark.catalog.tableExists(name) for name in tables)
    return {frozenset(v) for v in groups.values()},result.rounds


@pytest.mark.parametrize('method,groups',[
    ('connected_components',[{'a','b','c'},{'d'}]),('star',[{'a','b','c'},{'d'}]),
    ('center',[{'a','b'},{'c'},{'d'}]),('verified_merge',[{'a','b'},{'c'},{'d'}])])
def test_methods_handle_transitivity_veto_and_isolated_records(spark,method,groups):
    result,trace=run(spark,method)
    assert result=={frozenset(x) for x in groups}
    assert trace
    if method=='verified_merge': assert any(r.get('vetoed_proposals',0) for r in trace)


def test_incomplete_components_cannot_silently_pass(spark):
    with pytest.raises(ConvergenceError,match='within 1 rounds'):
        run(spark,'connected_components',max_rounds=1)
