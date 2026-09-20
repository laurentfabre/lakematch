"""Reproduce the observed Apps asynchronous creation/stop constraints offline."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from acceptance.lifecycle import wait_provisioned, stop_when_ready


def app(state, identity=False):
    value={'compute_status':{'state':state}}
    if identity:value['service_principal_client_id']='synthetic-app-id'
    return value


class Clock:
    def __init__(self):self.now=0
    def time(self):return self.now
    def sleep(self,seconds):self.now+=seconds


def test_creation_waits_for_both_identity_and_terminal_provisioning():
    states=iter([app('STARTING'),app('STARTING',True),app('STOPPED',True)])
    clock=Clock()
    result=wait_provisioned(lambda:next(states),sleep=clock.sleep,clock=clock.time)
    assert result==app('STOPPED',True) and clock.now==10


def test_stop_never_called_during_starting_or_after_stopped():
    states=iter([app('STARTING'),app('STARTING',True),app('ACTIVE',True),app('STOPPING',True),app('STOPPED',True)])
    clock=Clock();calls=[]
    result=stop_when_ready(lambda:next(states),lambda:calls.append(clock.now),sleep=clock.sleep,clock=clock.time)
    assert result==app('STOPPED',True) and calls==[10]
    calls.clear()
    stop_when_ready(lambda:app('STOPPED',True),lambda:calls.append('unexpected'))
    assert calls==[]


def test_provisioning_timeout_is_bounded():
    clock=Clock()
    with pytest.raises(TimeoutError):
        wait_provisioned(lambda:app('STARTING'),timeout=15,sleep=clock.sleep,clock=clock.time)
    assert clock.now==15
