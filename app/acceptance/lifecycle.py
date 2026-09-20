"""Finite provisioning/cleanup waits, independent of app data and credentials."""
import time


def wait_provisioned(get_app, *, timeout=300, sleep=time.sleep, clock=time.monotonic):
    deadline = clock() + timeout
    while clock() < deadline:
        app = get_app()
        state = app.get('compute_status', {}).get('state')
        if state in {'ERROR', 'FAILED'}:
            raise RuntimeError(f'App provisioning failed: {state}')
        if app.get('service_principal_client_id') and state in {'STOPPED', 'ACTIVE'}:
            return app
        sleep(5)
    raise TimeoutError('App identity/compute provisioning exceeded its deadline')


def stop_when_ready(get_app, stop_app, *, timeout=300, sleep=time.sleep, clock=time.monotonic):
    deadline = clock() + timeout
    requested = False
    while clock() < deadline:
        app = get_app()
        state = app.get('compute_status', {}).get('state')
        if state == 'STOPPED':
            return app
        # The Apps API rejects stop during initial STARTING. Wait for the
        # observed state change instead of repeating the unsupported request.
        if state not in {'STARTING', 'STOPPING'} and not requested:
            stop_app()
            requested = True
        sleep(5)
    raise TimeoutError('App did not reach STOPPED within the cleanup deadline')
