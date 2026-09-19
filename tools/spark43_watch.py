#!/usr/bin/env python3
"""spark43_watch.py — tell Laurent when Apache Spark 4.3 is released (asked 2026-09-19, goals/goal_zingg_rewrite.md).

Why it matters: Spark 4.3 adds `jaro_winkler_similarity` as a BUILT-IN SQL function (SPARK-57253). Until then
Jaro-Winkler in lakematch is a Python/JVM UDF, which Photon never runs; from 4.3 it can move to the built-in. Whether
Photon then accelerates it is NOT documented and has to be measured.

Weekly from launchd (com.lf.spark43-watch). A release = a final `pyspark` 4.3.x on PyPI or a `spark-4.3.*` directory
on dlcdn.apache.org. On the first detection: write an .ics with an alarm, `open` it (the house way to reach a human),
leave a marker so it never fires twice, log one line. Offline is not a fault: exit 0 and try next week.

    python3 Lake/mdm/spark43_watch.py            # the real check
    python3 Lake/mdm/spark43_watch.py --dry-run  # pretend 4.3.0 exists; write the .ics, open nothing, no marker
"""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "Reports" / "output"
MARKER = OUT / ".spark43_released"
ICS = OUT / "spark43_released.ics"
LOG = OUT / "spark43_watch.log"


def fetch(url: str) -> str | None:
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001 — offline or a transient error: not a fault
        return None


def released() -> str | None:
    pypi = fetch("https://pypi.org/pypi/pyspark/json")
    if pypi:
        finals = [v for v in json.loads(pypi)["releases"] if re.fullmatch(r"4\.(\d+)\.\d+", v) and int(v.split(".")[1]) >= 3]
        if finals:
            return "pyspark " + sorted(finals, key=lambda v: [int(x) for x in v.split(".")])[0] + " on PyPI"
    listing = fetch("https://dlcdn.apache.org/spark/")
    if listing:
        hit = re.search(r"spark-4\.(?:[3-9]|\d{2,})\.\d+", listing)
        if hit:
            return hit.group(0) + " on dlcdn.apache.org"
    if pypi is None and listing is None:
        return "OFFLINE"
    return None


def ics(what: str) -> str:
    start = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=10)
    stamp = lambda t: t.strftime("%Y%m%dT%H%M%SZ")  # noqa: E731
    text = ("Apache Spark 4.3 is out (" + what + "). lakematch: Jaro-Winkler can move from a UDF to the built-in "
            "jaro_winkler_similarity (SPARK-57253). Measure whether Photon accelerates it before changing any default. "
            "See goals/goal_zingg_rewrite.md.")
    return "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//lf//spark43-watch//EN", "BEGIN:VEVENT",
        "UID:spark43-released@lf", "DTSTAMP:" + stamp(dt.datetime.now(dt.timezone.utc)),
        "DTSTART:" + stamp(start), "DTEND:" + stamp(start + dt.timedelta(minutes=15)),
        "SUMMARY:Spark 4.3 released — Jaro-Winkler is now a Spark built-in", "DESCRIPTION:" + text,
        "BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:Spark 4.3 released", "TRIGGER:-PT0M", "END:VALARM",
        "END:VEVENT", "END:VCALENDAR", ""])


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    dry = "--dry-run" in sys.argv
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if MARKER.exists() and not dry:
        return 0
    what = "pyspark 4.3.0 on PyPI (simulated)" if dry else released()
    line = f"{now} " + ("not released yet" if what is None else what)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + ("  [dry run]" if dry else "") + "\n")
    print(line)
    if what in (None, "OFFLINE"):
        return 0
    ICS.write_text(ics(what), encoding="utf-8")
    if not dry:
        MARKER.write_text(line + "\n", encoding="utf-8")
        subprocess.run(["open", str(ICS)], check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
