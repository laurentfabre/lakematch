"""Deployment evidence excludes credentials and rejects stale source or readiness."""
import base64
import hashlib
from pathlib import Path
import sys
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from lakefusion_startup_run import deployment_ready, instance_qualification, redact_app_logs, verify_uploaded_payload
from workflow_retained import RetainedStateError


def test_credentials_removed_while_startup_failure_remains():
    value = uuid4().hex
    jwt = 'eyJ'+value+'.'+value+'.'+value
    raw = '\n'.join(['Traceback (most recent call last):',
        'client_secret='+value, 'Authorization: Bearer '+value,
        '"refresh_token": "'+value+'"', jwt, 'dapi'+value,
        'https://operator:'+value+'@example.invalid',
        'ContractError: Injected resources do not match the selected binding'])
    redacted = redact_app_logs(raw)
    assert value not in redacted
    assert 'Traceback' in redacted
    assert 'ContractError: Injected resources do not match the selected binding' in redacted


def test_readback_rejects_stale_configuration_even_when_other_files_match():
    files = {'app.yaml': b'endpoint: selected', 'binding.json': b'{}', 'wheels/runtime.whl': b'wheel'}
    manifest = {'app/'+name: {'sha256': hashlib.sha256(value).hexdigest(), 'bytes': len(value)}
                for name, value in files.items()}
    root = '/Workspace/synthetic/app'
    def export(path):
        return base64.b64encode(files[path.removeprefix(root+'/')]).decode()
    assert len(verify_uploaded_payload(export, root, manifest)) == 3
    files['app.yaml'] = b'endpoint: previous'
    with pytest.raises(RetainedStateError, match='app.yaml'):
        verify_uploaded_payload(export, root, manifest)


@pytest.mark.parametrize('state', ['SUCCEEDED', 'FAILED'])
def test_previous_deployment_cannot_satisfy_or_fail_selected_readiness(state):
    app = {'active_deployment': {'deployment_id': 'previous', 'status': {'state': state}},
           'compute_status': {'state': 'ACTIVE'}, 'app_status': {'state': 'RUNNING'}}
    assert deployment_ready(app, 'selected') is False
    app['active_deployment']['deployment_id'] = 'selected'
    if state == 'SUCCEEDED':
        assert deployment_ready(app, 'selected') is True
        app['app_status']['state'] = 'UNAVAILABLE'
        assert deployment_ready(app, 'selected') is False
    else:
        with pytest.raises(RetainedStateError, match='Selected application deployment failed'):
            deployment_ready(app, 'selected')


def test_missing_instance_telemetry_never_passes_and_needs_explicit_collection_mode():
    app = {'compute_size': 'MEDIUM', 'compute_status': {}}
    with pytest.raises(RetainedStateError, match='Singleton'):
        instance_qualification(app)
    assert instance_qualification(app, collect_when_unreported=True)['status'] == 'unqualified'
    app['compute_status']['active_instances'] = 1
    assert instance_qualification(app)['status'] == 'passed'


@pytest.mark.parametrize('count', [0, 2, -1, True, '1'])
def test_collection_mode_never_accepts_observed_instance_drift(count):
    app = {'compute_size': 'MEDIUM', 'compute_status': {'active_instances': count}}
    with pytest.raises(RetainedStateError, match='Observed instance'):
        instance_qualification(app, collect_when_unreported=True)


@pytest.mark.parametrize('change', [{'compute_size': 'LARGE'}, {'compute_min_instances': 2},
                                  {'compute_max_instances': 2}])
def test_collection_mode_never_accepts_a_larger_configured_envelope(change):
    with pytest.raises(RetainedStateError):
        instance_qualification({'compute_size': 'MEDIUM', **change}, collect_when_unreported=True)
