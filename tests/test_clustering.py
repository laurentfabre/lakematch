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
    with pytest.raises(ConvergenceError,match='within 1 rounds') as failure:
        run(spark,'connected_components',max_rounds=1)
    assert len(failure.value.rounds) == 1


def test_component_shortcuts_converge_on_long_paths_without_crossing_components(spark):
    config=from_dict({'entity':{'fields':{'name':{'type':'person_name'}}},
        'decision':{'threshold':.9},'cluster':{'method':'connected_components','max_rounds':8}})
    names=[f'n{i:03d}' for i in range(64)]
    vertices=spark.createDataFrame([(name,) for name in [*names,'isolated']], 'rec_id string')
    edges=spark.createDataFrame([(names[i+1],names[i],.99) for i in range(63) if i != 31],
        'a_id string,b_id string,p double')
    with Materializer(spark,config,probe(spark)) as materializer:
        result=resolve(vertices,edges,config,materializer)
        actual={row.rec_id:row.cluster for row in result.membership.collect()}
        tables=[event['table'] for event in materializer.events]
    assert actual=={'isolated':'isolated', **{name:names[0 if i < 32 else 32] for i,name in enumerate(names)}}
    assert len(result.rounds) <= 8
    assert result.rounds[-1]['changed_vertices'] == 0
    assert not any(spark.catalog.tableExists(name) for name in tables)
