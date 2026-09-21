"""One opt-in NL count check of the deployed space against direct warehouse SQL."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from workspace_support import NAMESPACE, client, sql


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    w = client(args.profile)
    result = subprocess.run(["databricks", "bundle", "summary", "-t", "dev", "--profile", args.profile,
                             "--output", "json"], cwd=ROOT / "genie", check=True,
                            capture_output=True, text=True, timeout=60)
    space_id = json.loads(result.stdout)["resources"]["genie_spaces"]["matching"]["id"]
    space = w.genie.get_space(space_id)
    question = "How many accepted matches (links) are there?"
    statement = f"SELECT COUNT(*) AS links FROM {NAMESPACE}.lm_links_all"
    report = {"observed_at": datetime.now(timezone.utc).isoformat(), "profile": args.profile,
              "space_id": space_id, "warehouse_id": space.warehouse_id, "question": question,
              "direct_sql": statement, "status": "running",
              "scope": "standalone Genie count smoke; does not test delegated app access or all benchmarks"}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    try:
        direct = sql(w, space.warehouse_id, statement)
        report["direct_count"] = int(direct[0][0])
        report["direct_result_rows"] = len(direct)
        message = w.genie.start_conversation_and_wait(space_id, question, timeout=timedelta(minutes=3))
        report.update(conversation_id=message.conversation_id, message_id=message.id)
        queries = [attachment for attachment in message.attachments if attachment.query]
        if len(queries) != 1:
            raise RuntimeError("Expected one Genie query result")
        attachment = queries[0]
        response = w.genie.get_message_attachment_query_result(space_id, message.conversation_id,
                                                              message.id, attachment.attachment_id)
        rows = response.statement_response.result.data_array
        report.update(genie_sql=attachment.query.query, genie_result_rows=len(rows))
        if len(rows) != 1 or len(rows[0]) != 1:
            raise RuntimeError("Expected a single scalar count from Genie")
        report["genie_count"] = int(rows[0][0])
        if report["genie_count"] != report["direct_count"]:
            raise AssertionError("Genie and direct SQL disagree")
        report["status"] = "passed"
    except BaseException as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
