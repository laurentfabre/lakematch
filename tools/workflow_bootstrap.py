"""Operator-only setup for a fresh, dedicated workflow database.

Serving credentials never run this module. Existing schemas are refused; a
later redeployment verifies their recorded state instead of reseeding them.
"""
from pathlib import Path
import json

from lakematch.mastering.access_registry import PostgresAccessRegistry, grant_workflow_role
from lakematch.mastering.contracts import DomainContract
from lakematch.mastering.identity_contract import IdentityContext, SourceRef
from lakematch.mastering.identity_registry import PostgresIdentityRegistry
from lakematch.mastering.registry import PostgresRegistry, apply_migrations

ROOT = Path(__file__).resolve().parents[1]


def bootstrap(connect, serving_role, principal):
    domain = DomainContract.from_dict(json.loads(
        (ROOT/'examples/mastering/company_pilot/domain.json').read_text()))
    with connect() as connection:
        if connection.execute("SELECT to_regnamespace('lm_control')").fetchone()[0] is not None:
            raise ValueError('Fresh control schema required; preserve existing data')
    with connect() as connection:
        migrations = apply_migrations(connection, ROOT/'app/migrations/mastering')
        grant_workflow_role(connection, serving_role)
    registry = PostgresRegistry(connect)
    # Preserve the fixture's author separately from the operator importing its
    # already-approved contract. This is not proof of two authenticated users.
    registry.submit_domain(domain, actor='synthetic:company-pilot-fixture-v1', expected_latest=0)
    registry.transition('domain', 'company', 'company', 1, state='approved', expected_revision=1,
                        actor=principal, reason='Approved synthetic pilot deployment')
    identities = PostgresIdentityRegistry(connect, IdentityContext('company', 1, domain.sha256))
    identity = identities.allocate([SourceRef('erp_vendor', 'deployment-fixture-001'),
                                    SourceRef('crm_account', 'deployment-fixture-001')],
                                   actor=principal, reason='Synthetic deployment fixture',
                                   key='deployment-identity-v1')
    master = identity['result']['master_id']
    grants = [{'role': 'steward', 'fields': None, 'object_ids': [master]}]
    receipt = PostgresAccessRegistry(connect).replace(principal, 'company', grants,
        expected_revision=0, actor=principal, reason='Synthetic deployment acceptance',
        key='deployment-grant-v1')
    return {'migrations': migrations, 'domain_sha256': domain.sha256,
            'master_id': master, 'principal': principal, 'grant': receipt, 'grants': grants}
