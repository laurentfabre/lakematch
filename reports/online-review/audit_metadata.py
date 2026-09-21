"""Read-only metadata check of the user's selected workspace; no SQL or compute starts."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

PROFILE = "fevm-gdpr2"
OUT = Path(__file__).resolve().parent


def read(*args):
    command = ["databricks", *args, "--profile", PROFILE, "--output", "json"]
    result = subprocess.run(command, capture_output=True, text=True, timeout=45)
    if result.returncode:
        # Do not write authentication headers, raw data or credentials to receipts.
        raise RuntimeError(f"Metadata command {args[:2]} failed (exit {result.returncode})")
    return json.loads(result.stdout)


def rows(value, key):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return value.get(key, []) or []
    raise ValueError("Unexpected metadata response shape")


def selected(value, keys):
    return {key: value.get(key) for key in keys}


def genie_summary(space):
    space_id = space["space_id"]
    detail = read("genie", "get-space", space_id, "--include-serialized-space")
    raw = detail.get("serialized_space")
    config = json.loads(raw) if isinstance(raw, str) else (raw or {})
    result = {"space_id": space_id, "serialized_space_available": bool(raw),
              "top_level_setting_fields": selected(detail, ["format_assistance", "entity_matching", "enable_format_assistance", "enable_entity_matching"]),
              "table_count": 0, "configured_columns": 0, "format_assisted_columns": 0,
              "format_assisted_without_explicit_entity_matching": [],
              "entity_matching_columns": 0}
    tables = config.get("data_sources", {}).get("tables", [])
    result["table_count"] = len(tables)
    for ti, table in enumerate(tables):
        for ci, column in enumerate(table.get("column_configs", [])):
            result["configured_columns"] += 1
            enabled = column.get("enable_format_assistance") is True
            matching = column.get("enable_entity_matching") is True
            result["format_assisted_columns"] += enabled
            result["entity_matching_columns"] += matching
            if enabled and not matching:
                # Record indices only: no table names, column names, sample data,
                # SQL examples, questions or conversation contents are exported.
                result["format_assisted_without_explicit_entity_matching"].append({
                    "table_index": ti, "column_index": ci,
                    "enable_entity_matching": column.get("enable_entity_matching")})
    return result


def main():
    report = {"observed_at": datetime.now(timezone.utc).isoformat(), "profile": PROFILE,
              "mode": "read-only metadata; no SQL, conversations, mutations or compute starts",
              "errors": {}}
    jobs = {"warehouses": ("warehouses", "list"), "global_init_scripts": ("global-init-scripts", "list"),
            "clusters": ("clusters", "list"), "genie_spaces": ("genie", "list-spaces")}
    values = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        pending = {name: pool.submit(read, *command) for name, command in jobs.items()}
        for name, task in pending.items():
            try:
                values[name] = task.result()
            except Exception as error:
                report["errors"][name] = str(error)
    if "warehouses" in values:
        report["warehouses"] = [selected(r, ["id", "name", "state", "auto_stop_mins", "warehouse_type",
            "enable_serverless_compute", "channel", "min_num_clusters", "max_num_clusters"])
            for r in rows(values["warehouses"], "warehouses")]
    if "global_init_scripts" in values:
        report["global_init_scripts"] = [selected(r, ["script_id", "name", "enabled", "position"])
            for r in rows(values["global_init_scripts"], "scripts")]
    if "clusters" in values:
        report["clusters"] = [selected(r, ["cluster_id", "cluster_name", "state", "cluster_source"])
            for r in rows(values["clusters"], "clusters")]
    if "genie_spaces" in values:
        spaces = rows(values["genie_spaces"], "spaces")
        report["genie_spaces"] = []
        if len(spaces) > 10:
            report["errors"]["genie_details"] = "Inventory exceeded the bounded 10-space audit; not inspected"
        else:
            with ThreadPoolExecutor(max_workers=3) as pool:
                pending = {space["space_id"]: pool.submit(genie_summary, space) for space in spaces}
                for space_id, task in pending.items():
                    try:
                        report["genie_spaces"].append(task.result())
                    except Exception as error:
                        report["errors"]["genie:" + space_id] = str(error)
    destination = OUT / "workspace-metadata-20260921.json"
    destination.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"receipt": str(destination), "profile": PROFILE,
        "warehouses": report.get("warehouses"),
        "global_init_script_count": len(report.get("global_init_scripts", [])),
        "cluster_count": len(report.get("clusters", [])),
        "genie_spaces": [{"space_id": s["space_id"],
            "format_assisted_columns": s["format_assisted_columns"],
            "without_explicit_entity_matching": len(s["format_assisted_without_explicit_entity_matching"])}
            for s in report.get("genie_spaces", [])], "errors": report["errors"]}, indent=2))


if __name__ == "__main__":
    main()
