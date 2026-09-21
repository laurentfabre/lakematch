#!/usr/bin/env python3
"""One bounded Unity Gateway discovery/inference smoke; no service creation."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a fresh evidence path")
    report = {
        "schema_version": 1, "phase": "LF-A", "profile": args.profile,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "interface": "/ai-gateway/mlflow/v1/chat/completions",
        "bounds": {"listed_services": 100, "inference_requests": 1,
                   "input_utf8_bytes": 1024, "max_output_tokens": 128,
                   "request_timeout_seconds": 45, "inference_retries": 0},
        "resource_mutations": [], "inference_requests": 0,
        "billing": {"status": "unreconciled", "actual_currency": None},
        "status": "started",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    started = time.monotonic()
    try:
        result = subprocess.run([
            "databricks", "ai-gateway", "list-model-services", "--parent", "schemas/system.ai",
            "--page-size", "100", "--limit", "100", "--view", "BASIC",
            "--profile", args.profile, "--output", "json"],
            capture_output=True, text=True, timeout=45)
        if result.returncode:
            # Do not persist CLI stderr or auth headers. Only stable service error codes.
            codes = re.findall(r"\b(?:PERMISSION_DENIED|FEATURE_DISABLED|NOT_FOUND|UNIMPLEMENTED|INVALID_PARAMETER_VALUE|UNAUTHENTICATED)\b",
                               result.stderr)
            report.update(status="metadata_unavailable", cli_exit_code=result.returncode,
                          service_error_codes=sorted(set(codes)))
            return 1
        raw = json.loads(result.stdout)
        services = raw if isinstance(raw, list) else raw.get("model_services", [])
        report["services"] = [{"name": s.get("name"), "supported_api_types": s.get("supported_api_types", [])}
                              for s in services]
        # Resolve the documented default from this bounded live list, not a hard-coded model.
        names = [s.get("name", "").removeprefix("model-services/") for s in services]
        sonnets = [n for n in names if re.fullmatch(r"system\.ai\.claude-sonnet-\d+(?:-\d+)*", n)]
        if not sonnets:
            report["status"] = "no_discovered_sonnet_service"
            return 1
        model = max(sonnets, key=lambda n: tuple(map(int, re.findall(r"\d+", n))))
        report["model_service"] = model
        messages = [{"role": "user", "content": (
            'Synthetic connectivity check only. Return exactly the JSON object '
            '{"company":"Example Orchard","country":"FR"}.')}]
        assert len(json.dumps(messages).encode()) <= 1024
        body = {"model": model, "messages": messages, "max_tokens": 128}
        report["request_sha256"] = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        from databricks.sdk.core import Config
        import requests
        cfg = Config(profile=args.profile)
        headers = {**cfg.authenticate(), "Content-Type": "application/json"}
        report["inference_requests"] = 1
        call_started = time.monotonic()
        response = requests.post(cfg.host.rstrip("/") + report["interface"],
                                 headers=headers, json=body, timeout=(10, 45), allow_redirects=False)
        report["inference_wall_seconds"] = round(time.monotonic() - call_started, 3)
        report["http_status"] = response.status_code
        for key in ("x-request-id", "x-databricks-request-id"):
            if key in response.headers:
                report.setdefault("request_ids", {})[key] = response.headers[key]
        if response.status_code != 200:
            report["status"] = "inference_unavailable"
            # The request contains only the fixed synthetic smoke prompt. Persist
            # the service diagnostic, never the headers or credential objects.
            try:
                failure = response.json()
                detail = failure.get("error", failure)
                if isinstance(detail, dict):
                    report["service_error"] = {k: str(detail[k])[:1200]
                                               for k in ("error_code", "code", "message", "type")
                                               if k in detail}
            except (ValueError, AttributeError):
                report["service_error"] = {"message": "Non-JSON error body withheld"}
            return 1
        value = response.json()
        content = value["choices"][0]["message"]["content"]
        report["usage"] = {k: value.get("usage", {}).get(k)
                           for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
        report["response_model"] = value.get("model")
        report["response_sha256"] = hashlib.sha256(content.encode()).hexdigest()
        valid = json.loads(content) == {"company": "Example Orchard", "country": "FR"}
        report["structured_response_valid"] = valid
        report["status"] = "inference_verified" if valid else "response_invalid"
        return int(not valid)
    except Exception as error:
        report.update(status="probe_failed", error_type=type(error).__name__)
        return 1
    finally:
        report.update(ended_at=datetime.now(timezone.utc).isoformat(),
                      wall_seconds=round(time.monotonic() - started, 3),
                      limitations="Connectivity only; no matching benefit, app identity or billing acceptance")
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({k: report.get(k) for k in ("status", "model_service", "inference_requests", "usage", "http_status")}))


if __name__ == "__main__":
    raise SystemExit(main())
