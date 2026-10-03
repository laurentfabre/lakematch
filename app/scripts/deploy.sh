#!/usr/bin/env bash
# Deploy the arbitration app to Databricks (ZR-7): bash app/scripts/deploy.sh [engine-config] [profile]
#
# 1. refuses unless the engine config turns paid_features.app on (Databricks Apps compute bills while the app runs);
# 2. builds (apx build: front end + wheel; must stay under the 10 MB app file limit), deploys the bundle, starts the app;
# 3. grants the app's service principal what it needs in the schema: read the queue and the run history, append to
#    the label table (created empty by the engine's train / review tasks, so the app never needs CREATE).
# The warehouse is shared (Alfred uses it too): this script stops it when it started it for the grants.
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
cfg="${1:-$here/../examples/febrl4_databricks.yaml}"
profile="${2:-fourth-pat}"
schema="workspace.lakematch"
wh="79dfcc5bc7019dd3"

on="$("$here/../.venv/bin/python" -c 'import sys; from lakematch.config import load; print(load(sys.argv[1]).get("paid_features.app"))' "$cfg")"
[[ "$on" == True ]] || { echo "paid_features.app is off in $cfg: not deploying (Databricks Apps compute is billed)"; exit 3; }

cd "$here"
apx build < /dev/null
mb="$(du -sk .build | awk '{printf "%.2f", $1/1024}')"
echo "bundle .build: ${mb} MB (limit 10 MB)"
databricks bundle deploy -t dev --profile "$profile"
databricks bundle run lakematch -t dev --profile "$profile"

sp="$(databricks apps get lakematch --profile "$profile" -o json | python3 -c 'import json,sys; print(json.load(sys.stdin)["service_principal_client_id"])')"
was="$(databricks warehouses get "$wh" --profile "$profile" -o json | python3 -c 'import json,sys; print(json.load(sys.stdin)["state"])')"
for stmt in "GRANT USE CATALOG ON CATALOG workspace TO \`$sp\`" \
            "GRANT USE SCHEMA ON SCHEMA $schema TO \`$sp\`" \
            "GRANT SELECT ON TABLE $schema.lm_review_queue TO \`$sp\`" \
            "GRANT SELECT ON TABLE $schema.lm_review_runs TO \`$sp\`" \
            "GRANT SELECT, MODIFY ON TABLE $schema.lm_review_labels TO \`$sp\`"; do
  databricks experimental aitools tools query "$stmt" --warehouse "$wh" --profile "$profile" >/dev/null && echo "ok  $stmt"
done
[[ "$was" == STOPPED ]] && databricks warehouses stop "$wh" --profile "$profile" --no-wait >/dev/null && echo "warehouse stopped again"
databricks apps get lakematch --profile "$profile" -o json | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["url"], d["app_status"]["state"], d["compute_status"]["state"])'
