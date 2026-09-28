#!/usr/bin/env bash
# verify_simbeat.sh <1..4> — finish lines of goals/goal_beat_jw.md (beat Jaro-Winkler with Spark built-ins).
# Exit 0 = the phase is landed; 1 = not, every failing check listed; 2 = usage. Reads, never writes.
set -u
REPO="${LAKEMATCH_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PHASE="${1:-}"
[[ "$PHASE" =~ ^[1-4]$ ]] || { echo "usage: verify_simbeat.sh <1..4>"; exit 2; }
FAIL=0
fail() { echo "✗ $*"; FAIL=1; }
ok()   { echo "✓ $*"; }
TMP="$(mktemp -d "${TMPDIR:-/tmp}/verify_simbeat.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
export PYTHONDONTWRITEBYTECODE=1
cd "$REPO" || { echo "✗ no repo at $REPO"; exit 1; }
PY="$REPO/.venv/bin/python"
# shellcheck disable=SC1091
[[ -f scripts/env.sh ]] && source scripts/env.sh
CAND=spec/research/sota_candidates.json
SIM=bench/results/simbeat.json

pyjudge() {   # runs a python check that prints "OK ..." or "BAD ..."
  local label="$1"; shift
  local r; r="$("$PY" - "$@" 2>&1)"
  [[ "$r" == OK* ]] && ok "$label: ${r#OK }" || fail "$label: ${r#BAD }"
}

pytest_both() {   # pytest_both <-k expr> <label>
  local pass
  for pass in 0 1; do
    local kind=$([[ $pass == 1 ]] && echo Connect || echo classic)
    if LAKEMATCH_TEST_CONNECT=$pass perl -e 'alarm shift; exec @ARGV' 900 "$PY" -m pytest -p no:cacheprovider ${1:+-k "$1"} \
         > "$TMP/pt.log" 2>&1 && grep -qE '[1-9][0-9]* passed' "$TMP/pt.log"; then
      ok "$2 ($kind): $(grep -E '[0-9]+ passed' "$TMP/pt.log" | tail -1)"
    else fail "$2 ($kind): $(grep -E 'passed|failed|error|deselected' "$TMP/pt.log" | tail -1)"; fi
  done
}

phase1() {
  [[ -f spec/research/string_similarity_sota_2026.md ]] && ok "digest present" || fail "spec/research/string_similarity_sota_2026.md missing"
  [[ -f "$CAND" ]] || { fail "$CAND missing"; return; }
  pyjudge "catalogue" "$CAND" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1])); bad = []
refs, ms = d.get("references", []), d.get("measures", [])
ids = {r.get("id") for r in refs}
urls = [r.get("url", "") for r in refs]
if len(refs) < 20: bad.append(f"{len(refs)} references (need 20)")
if len(set(urls)) != len(urls): bad.append("duplicate reference URLs")
if any(not u.startswith(("http://", "https://")) for u in urls): bad.append("a reference without an http(s) URL")
if sum(1 for r in refs if isinstance(r.get("year"), int) and r["year"] >= 2021) < 5: bad.append("fewer than 5 references from 2021 or later")
if any(r.get("kind") not in ("paper", "standard", "library-doc") for r in refs): bad.append("reference kind outside paper|standard|library-doc")
if len(ms) < 15: bad.append(f"{len(ms)} measures (need 15)")
cats = {"edit", "token", "hybrid", "phonetic", "alignment", "learned"}
for m in ms:
    n = m.get("name", "?")
    for k in ("name", "category", "field_types", "refs", "evidence", "builtin_expressible", "sketch", "shortlisted"):
        if k not in m: bad.append(f"{n}: no {k}")
    if m.get("category") not in cats: bad.append(f"{n}: category {m.get('category')}")
    if not m.get("refs") or any(x not in ids for x in m.get("refs", [])): bad.append(f"{n}: refs not in references")
    if len(str(m.get("evidence", ""))) < 40: bad.append(f"{n}: evidence too thin")
missing = cats - {m.get("category") for m in ms}
if missing: bad.append(f"no measure in categories {sorted(missing)}")
short = [m for m in ms if m.get("shortlisted")]
if len(short) < 6: bad.append(f"{len(short)} shortlisted (need 6)")
if any(not m.get("builtin_expressible") for m in short): bad.append("a shortlisted measure is not built-in expressible")
if len({m.get('category') for m in short}) < 3: bad.append("shortlist covers fewer than 3 categories")
from lakematch.config import FAMILIES
from lakematch.features import FAMILY_OF_PREFIX
fams = [m.get("family") for m in short]; prefs = [m.get("prefix") for m in short]
if len(set(fams)) != len(fams) or None in fams: bad.append("shortlisted families missing or not unique")
if len(set(prefs)) != len(prefs) or None in prefs: bad.append("shortlisted prefixes missing or not unique")
print("BAD " + " | ".join(bad) if bad else f"OK {len(refs)} references, {len(ms)} measures, {len(short)} shortlisted: {', '.join(fams)}")
EOF
}

phase2() {
  [[ -f "$CAND" ]] || { fail "$CAND missing (SIM-1 first)"; return; }
  pyjudge "families registered, off by default" "$CAND" <<'EOF'
import json, sys
from lakematch import config
from lakematch.config import FAMILIES, DEFAULTS
from lakematch.features import FAMILY_OF_PREFIX, active_families
short = [m for m in json.load(open(sys.argv[1]))["measures"] if m.get("shortlisted")]
bad = []
default_on = active_families(config.build({}))
for m in short:
    if m["family"] not in FAMILIES: bad.append(f"{m['family']} not in config.FAMILIES")
    if FAMILY_OF_PREFIX.get(m["prefix"]) != m["family"]: bad.append(f"prefix {m['prefix']} does not map to {m['family']}")
    if m["family"] in default_on: bad.append(f"{m['family']} is on by default before SIM-4")
print("BAD " + " | ".join(bad) if bad else f"OK {len(short)} families, all opt-in")
EOF
  local fam
  for fam in $("$PY" -c "import json;print(' '.join(m['family'] for m in json.load(open('$CAND'))['measures'] if m.get('shortlisted')))" 2>/dev/null); do
    pytest_both "test_sota_$fam" "reference-value tests for $fam"
  done
  pytest_both "test_sota_plan_is_builtin" "every new family compiles with no Python UDF"
  pytest_both "" "full suite"
}

verdict_check() {
  "$PY" - "$SIM" "$CAND" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1])); short = [m for m in json.load(open(sys.argv[2]))["measures"] if m.get("shortlisted")]
CORPORA = ("febrl4_half_unmatched", "bpid", "abt_buy", "leipzig_affiliations")
bad = []
if d.get("selected_on") != "validation": bad.append("selected_on is not validation")
rows = d.get("valid", {})
need = ["levenshtein", "jaro_winkler", "both"] + [f"levenshtein + {m['family']}" for m in short] + ["chosen"]
for name in need:
    for c in CORPORA:
        r = rows.get(name, {}).get(c)
        if not r or not isinstance(r.get("f1"), (int, float)) or len(r.get("ci95", [])) != 2:
            bad.append(f"VALID row '{name}' / {c} missing or without interval")
for name, per in rows.items():
    if name not in ("jaro_winkler", "both") and not all(v.get("plan_udf_free") for v in per.values()):
        bad.append(f"row '{name}': plan not recorded UDF-free")
if not d.get("forward_selection"): bad.append("no forward-selection trace")
chosen = d.get("chosen_families") or []
if not chosen or not set(chosen) <= {m["family"] for m in short}: bad.append("chosen set empty or outside the shortlist")
t = d.get("test", {})
if not {"chosen", "jaro_winkler"} <= set(t) or len(t.get("delta_ci95", [])) != 2: bad.append("TEST confirmation incomplete")
if bad:
    print("BAD " + " | ".join(bad)); sys.exit()
mean = lambda n: sum(rows[n][c]["f1"] for c in CORPORA) / len(CORPORA)
beaten = (mean("chosen") > mean("jaro_winkler")
          and rows["chosen"]["abt_buy"]["f1"] >= rows["jaro_winkler"]["abt_buy"]["f1"]
          and all(rows["chosen"][c]["f1"] >= rows["levenshtein"][c]["f1"] - 0.005 for c in CORPORA)
          and t["chosen"]["mean_f1"] >= t["jaro_winkler"]["mean_f1"])
want = "beaten" if beaten else "not_beaten"
if d.get("verdict") != want:
    print(f"BAD recorded verdict '{d.get('verdict')}' but the rows say '{want}'"); sys.exit()
print(f"OK verdict {want}: VALID mean chosen {mean('chosen'):.4f} vs JW {mean('jaro_winkler'):.4f} vs lev {mean('levenshtein'):.4f}; "
      f"TEST {t['chosen']['mean_f1']:.4f} vs {t['jaro_winkler']['mean_f1']:.4f}, Δ CI {t['delta_ci95']}")
EOF
}

phase3() {
  [[ -f bench/simbeat.py ]] && ok "bench/simbeat.py present" || fail "bench/simbeat.py missing"
  [[ -f bench/SIMBEAT.md ]] && ok "bench/SIMBEAT.md present" || fail "bench/SIMBEAT.md missing"
  [[ -f "$SIM" && -f "$CAND" ]] || { fail "$SIM or $CAND missing"; return; }
  # Verify frozen models, predictions, inputs and physical plans without Spark
  # inference. Keep the independent arithmetic verdict check below as well.
  if "$PY" bench/simbeat.py audit --work-dir "$REPO/data/runs/simbeat" > "$TMP/audit.log" 2>&1; then
    ok "artifact-backed selection and TEST audit passes"
  else
    fail "artifact-backed audit: $(tail -1 "$TMP/audit.log")"
  fi
  local r; r="$(verdict_check 2>&1)"
  [[ "$r" == OK* ]] && ok "comparison complete, ${r#OK }" || fail "comparison: ${r#BAD }"
}

phase4() {
  [[ -f "$SIM" ]] || { fail "$SIM missing (SIM-3 first)"; return; }
  local r; r="$(verdict_check 2>&1)"
  [[ "$r" == "OK verdict beaten"* ]] || { fail "SIM-4 applies only to a 'beaten' verdict: ${r#OK }${r#BAD }"; return; }
  ok "verdict beaten"
  pyjudge "chosen families on by default, reports regenerated after simbeat" "$SIM" <<'EOF'
import json, sys
from lakematch import config
from lakematch.features import active_families
d = json.load(open(sys.argv[1])); bad = []
on = active_families(config.build({}))
missing = [f for f in d["chosen_families"] if f not in on]
if missing: bad.append(f"not on by default: {missing}")
t_sim = d.get("meta", {}).get("generated", "")
for f in ("bench/results/methods.json", "bench/results/ablation.json"):
    g = json.load(open(f)).get("meta", {}).get("generated", "")
    if not g or g <= t_sim: bad.append(f"{f} generated {g or '?'}, not after simbeat ({t_sim})")
print("BAD " + " | ".join(bad) if bad else f"OK {d['chosen_families']} on by default")
EOF
  local n
  for n in 1 2 3a; do
    if bash "$HOME/Projects/Personal/goals/verify_zr.sh" "$n" > "$TMP/zr$n.log" 2>&1; then ok "verify_zr.sh $n passes"
    else fail "verify_zr.sh $n: $(grep '^✗' "$TMP/zr$n.log" | head -2 | tr '\n' ' ')"; fi
  done
}

"phase$PHASE"
if [[ $FAIL -eq 0 ]]; then echo "ALL CHECKS PASS — SIM-$PHASE landed"; exit 0; fi
echo "NOT DONE — SIM-$PHASE"; exit 1
