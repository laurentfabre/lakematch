"""Build the pinned APX app and check the Databricks Apps file-size contract."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent


def main():
    version = subprocess.check_output(["apx", "--version"], text=True)
    if "apx 0.3.8" not in version:
        raise SystemExit("Install APX 0.3.8 before building this snapshot")
    pinned = {name: (ROOT / name).read_bytes() for name in ("package.json", "bun.lock", "uv.lock")}
    api = ROOT / "src/lakematch_review/ui/lib/api.ts"
    notice = "// Modified for lakematch on 2026-09-20 from the APX 0.3.8 scaffold.\n"
    # APX's UI build installs latest router dev tools. Build the checked-in UI
    # with locked Vite instead, then let APX package the wheel and deployment.
    for command in (["uv", "sync", "--frozen"], ["apx", "bun", "install", "--frozen-lockfile"],
                    ["apx", "build", "--skip-ui-build"],
                    ["apx", "bun", "run", "vite", "build", "--config", "vite.deploy.config.ts"],
                    ["apx", "build", "--skip-ui-build"]):
        subprocess.run(command, cwd=ROOT, check=True, timeout=240)
    if not api.read_text().startswith(notice):
        api.write_text(notice + api.read_text())
    if any((ROOT / name).read_bytes() != data for name, data in pinned.items()):
        raise SystemExit("Build changed a committed dependency file; inspect before deploying")
    files = [p for p in (ROOT / ".build").rglob("*") if p.is_file()]
    if not files or any(p.stat().st_size >= 10 * 1024 * 1024 for p in files):
        raise SystemExit("Empty build or file exceeds the campaign's 10 MiB Apps limit")
    print(f"APX build: {len(files)} files; largest {max(p.stat().st_size for p in files):,} bytes")


if __name__ == "__main__":
    main()
