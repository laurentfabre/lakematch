"""Lazy DQX row-rule adapter; optional imports and no workspace/client actions.

DQX 0.16's full engine constructor makes a workspace connectivity call. Use its
public DQRowRule expression API here so SDP definitions stay lazy and offline
native quality never imports DQX. Window predicates are projected before rules.
"""
from pyspark.sql import functions as F

from .native import QualityResult
from .rules import predicates


def apply_and_split(frame, config):
    try:
        from databricks.labs.dqx.check_funcs import sql_expression
        from databricks.labs.dqx.rule import DQRowRule
    except ImportError as exc:
        raise RuntimeError('quality.engine=dqx requires the optional databricks-labs-dqx==0.16.0 adapter environment') from exc
    rules = list(predicates(config))
    temporary = [f'lm_dqx_check_{index}' for index in range(len(rules))]
    if set(temporary) & set(frame.columns):
        raise ValueError('Input contains reserved DQX predicate columns')
    projected = frame.select('*', *[passed.alias(column) for column, (_, _, passed) in zip(temporary, rules)])
    reasons = []
    for column, (name, severity, _) in zip(temporary, rules):
        rule = DQRowRule(name=name, criticality=severity, check_func=sql_expression,
            check_func_kwargs={'expression': f'`{column}`', 'msg': name, 'name': name})
        failure = rule.get_check_condition()
        reasons.append(F.when(failure.isNotNull(), F.struct(F.lit(name).alias('check'),
                                                          F.lit(severity).alias('criticality'))))
    annotated = projected.withColumn('lm_reasons', F.filter(F.array(*reasons), lambda x: x.isNotNull())).drop(*temporary)
    invalid = F.exists('lm_reasons', lambda x: x['criticality'] == 'error')
    return QualityResult(annotated.filter(~invalid), annotated.filter(invalid))
