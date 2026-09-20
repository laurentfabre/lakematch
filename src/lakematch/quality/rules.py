"""Quality rule predicates shared by native and optional adapters."""
from pyspark.sql import Window, functions as F


def predicates(config):
    ident = config['entity']['id_column']
    checks = [
        {'name': 'id_required', 'kind': 'not_null', 'column': ident, 'criticality': 'error'},
        {'name': 'id_unique', 'kind': 'unique', 'column': ident, 'criticality': 'error'},
    ] + config['quality']['checks']
    names = set()
    for check in checks:
        if set(check) - {'name', 'kind', 'column', 'criticality', 'pattern', 'min', 'max', 'value'}:
            raise ValueError(f'Unknown quality check option: {check}')
        name, kind = check['name'], check['kind']
        severity = check.get('criticality', 'error')
        if not isinstance(name, str) or not name or name in names or severity not in {'error', 'warn'}:
            raise ValueError('Quality names must be nonempty and unique; criticality must be error or warn')
        names.add(name)
        column = check.get('column', ident)
        if column not in [ident, *config.fields]:
            raise ValueError(f'Quality check references unknown field: {column}')
        value = F.col(column)
        if kind == 'not_null':
            passed = value.isNotNull() & (F.length(F.trim(value.cast('string'))) > 0)
        elif kind == 'unique':
            passed = F.count(F.lit(1)).over(Window.partitionBy(column)) == 1
        elif kind == 'regex':
            passed = value.rlike(check['pattern'])
        elif kind == 'range':
            passed = value.try_cast('double').between(check['min'], check['max'])
        elif kind == 'min_rows':
            passed = F.count(F.lit(1)).over(Window.partitionBy(F.lit(1))) >= int(check['value'])
        else:
            raise ValueError(f'Unknown quality check kind: {kind}')
        yield name, severity, F.coalesce(passed, F.lit(False))
