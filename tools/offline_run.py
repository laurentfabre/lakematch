#!/usr/bin/env python3
"""Run under OS egress denial, proving it before invoking the normal CLI."""
import errno
import socket
import subprocess
import sys
import tempfile
from pathlib import Path


def assert_offline():
    with tempfile.TemporaryDirectory(prefix="lakematch-worker-socket-") as root:
        path = str(Path(root) / "worker.sock")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server, socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            server.bind(path)
            server.listen(1)
            client.connect(path)
            accepted, _ = server.accept()
            accepted.close()
        print("Verified local Unix worker sockets are available", flush=True)
    with socket.socket() as sock:
        sock.settimeout(2)
        try:
            sock.connect(("1.1.1.1", 443))
        except OSError as exc:
            if exc.errno not in (errno.EPERM, errno.EACCES):
                raise RuntimeError("No explicit OS network denial observed") from exc
            print("Verified OS denies non-loopback network access", flush=True)
        else:
            raise RuntimeError("Offline proof failed: external network connection was allowed")


def main():
    assert_offline()
    return subprocess.run([sys.executable, "-m", "lakematch.cli", "run", "--config", "examples/synthetic.yaml"]).returncode


if __name__ == "__main__":
    sys.exit(main())
