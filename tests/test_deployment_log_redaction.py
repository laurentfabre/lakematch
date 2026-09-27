"""Remote initialization evidence must not persist credentials from exceptions."""
from pathlib import Path
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from lakefusion_startup_run import redact_app_logs


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
