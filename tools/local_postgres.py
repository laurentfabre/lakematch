"""Owned local PostgreSQL fixture with a private Unix socket and TCP disabled."""
from contextlib import AbstractContextManager
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time


class LocalPostgres(AbstractContextManager):
    def __init__(self):
        self.binaries = {name: shutil.which(name) for name in ("initdb", "postgres")}
        if not all(self.binaries.values()):
            raise RuntimeError("Install local PostgreSQL to run the explicit integration checks")
        self.temporary = None
        self.server = None
        self.log = None
        self.cleanup = "not started"
        self.port = 55437  # Private socket path makes this independent of other fixtures.

    def connect(self):
        import psycopg
        return psycopg.connect(host=str(self.socket), port=self.port, user="lm_registry_test",
                               dbname="postgres", connect_timeout=3, autocommit=True,
                               application_name="lakematch-owned-local-test")

    def _start(self):
        self.log = (self.base / "postgres.log").open("a")
        self.server = subprocess.Popen([self.binaries["postgres"], "-D", str(self.data), "-k", str(self.socket),
            "-p", str(self.port), "-c", "listen_addresses=", "-c", "fsync=on", "-c", "max_connections=12"],
            stdout=self.log, stderr=self.log)
        deadline = time.monotonic() + 15
        while True:
            try:
                with self.connect() as connection:
                    connection.execute("SELECT 1")
                break
            except Exception:
                if self.server.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError("Owned PostgreSQL failed to start; inspect the fixture log")
                time.sleep(.05)

    def _stop(self):
        if self.server is not None:
            if self.server.poll() is None:
                self.server.send_signal(signal.SIGINT)
                try:
                    self.server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.server.kill()
                    self.server.wait(timeout=5)
            self.cleanup = "owned Postgres stopped" if self.server.returncode == 0 else f"owned Postgres exit {self.server.returncode}"
            self.server = None
        if self.log is not None:
            self.log.close()
            self.log = None

    def restart(self):
        self._stop()
        if self.cleanup != "owned Postgres stopped":
            raise RuntimeError(self.cleanup)
        self._start()

    def __enter__(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="lm-reg-pg-")
        self.base = Path(self.temporary.name)
        self.data, self.socket = self.base / "db", self.base / "s"
        self.socket.mkdir(mode=0o700)
        try:
            subprocess.run([self.binaries["initdb"], "-D", str(self.data), "-U", "lm_registry_test",
                "--auth-local=trust", "--auth-host=reject", "--no-locale", "--encoding=UTF8"],
                check=True, capture_output=True, timeout=30)
            self._start()
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *exc):
        self._stop()
        if self.temporary is not None:
            self.temporary.cleanup()
            self.temporary = None
        if self.cleanup not in {"not started", "owned Postgres stopped"}:
            raise RuntimeError(self.cleanup)
        return False
