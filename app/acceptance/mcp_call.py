"""Bounded APX MCP call using the server's JSON-RPC stdio transport."""
import json
from pathlib import Path
import subprocess
import sys
import signal

app_root = Path(__file__).resolve().parents[1]
p = subprocess.Popen(['apx', 'mcp'], cwd=app_root, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('APX MCP exceeded 60 seconds')))
signal.alarm(60)
try:
    def send(message):
        assert p.stdin is not None
        p.stdin.write(json.dumps(message) + '\n'); p.stdin.flush()
    def receive(request_id):
        assert p.stdout is not None
        for line in p.stdout:
            try: response = json.loads(line)
            except ValueError: continue
            if response.get('id') == request_id: return response
        raise RuntimeError('APX MCP closed without returning a result')
    send({'jsonrpc':'2.0', 'id':1, 'method':'initialize', 'params':{'protocolVersion':'2024-11-05', 'capabilities':{}, 'clientInfo':{'name':'lakematch-acceptance','version':'1'}}})
    receive(1)
    send({'jsonrpc':'2.0', 'method':'notifications/initialized'})
    if len(sys.argv) == 1:
        send({'jsonrpc':'2.0', 'id':2, 'method':'tools/list', 'params':{}})
    else:
        send({'jsonrpc':'2.0', 'id':2, 'method':'tools/call', 'params':{'name':sys.argv[1], 'arguments':json.loads(sys.argv[2]) if len(sys.argv)>2 else {}}})
    print(json.dumps(receive(2), indent=2))
finally:
    p.terminate()
    try: p.wait(timeout=5)
    except subprocess.TimeoutExpired: p.kill(); p.wait()
