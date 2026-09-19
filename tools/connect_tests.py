#!/usr/bin/env python3
"""Own a local Spark Connect server, run the same suite, always stop the server."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import pyspark
from lakematch.runtime import LOCAL_JAVA_OPTIONS


def main():
    root = Path(pyspark.__file__).parent
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    command = [str(root / "bin" / "spark-submit"), "--master", "local[2]",
               "--driver-java-options", LOCAL_JAVA_OPTIONS,
               "--conf", f"spark.connect.grpc.binding.port={port}",
               "--conf", "spark.connect.grpc.binding.address=127.0.0.1",
               "--conf", "spark.sql.shuffle.partitions=4", "--conf", "spark.ui.enabled=false",
               "--class", "org.apache.spark.sql.connect.service.SparkConnectServer",
               str(root / "jars" / "spark-connect_2.13-4.1.3.jar")]
    server = subprocess.Popen(command)
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if server.poll() is not None:
                raise RuntimeError(f"Connect server exited: {server.returncode}")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    break
            except OSError:
                time.sleep(.2)
        else:
            raise TimeoutError("Connect server did not bind within 60 seconds")
        env = {**os.environ, "LAKEMATCH_TEST_MODE": "connect", "LAKEMATCH_CONNECT_URL": f"sc://localhost:{port}"}
        return subprocess.run([sys.executable, "-m", "pytest", "-q", "--junitxml=experiments/tests-connect.xml"], env=env).returncode
    finally:
        server.terminate()
        try:
            server.wait(timeout=15)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()


if __name__ == "__main__":
    sys.exit(main())
