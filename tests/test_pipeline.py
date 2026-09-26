"""End to end on a small synthetic two-source task that requires rejecting: half the left records have no partner."""
import csv
import json
import random

from conftest import make_cfg
from lakematch.pipeline import run
from lakematch.runtime import Runtime

GIVEN = ["anna", "benoit", "claire", "david", "elise", "francois", "gaelle", "hugo", "ines", "jules", "karine",
         "louis", "margot", "nicolas", "olivia", "pierre", "quentin", "rose", "simon", "thea"]
SUR = ["martin", "bernard", "dubois", "thomas", "robert", "richard", "petit", "durand", "leroy", "moreau", "simon",
       "laurent", "lefebvre", "michel", "garcia", "david", "bertrand", "roux", "vincent", "fournier"]
STREETS = ["rue du bac", "avenue foch", "boulevard voltaire", "rue de la paix", "place d'italie", "quai de seine"]


def _typo(rng, s):
    if len(s) < 3 or rng.random() < 0.5:
        return s
    i = rng.randrange(len(s) - 1)
    return s[:i] + s[i + 1] + s[i] + s[i + 2:]


def _write(tmp_path, n=240):
    rng = random.Random(7)
    people = [{"rid": f"L{i:04d}", "given": rng.choice(GIVEN), "surname": rng.choice(SUR),
               "street": f"{rng.randint(1, 120)} {rng.choice(STREETS)}", "postcode": f"75{rng.randint(1, 20):03d}",
               "dob": f"19{rng.randint(40, 99)}{rng.randint(1, 12):02d}{rng.randint(1, 28):02d}"} for i in range(n)]
    right, truth = [], []
    for i, p in enumerate(people):
        if i % 2 == 0:                               # half the left records get a (noisy) partner
            rid = f"R{i:04d}"
            right.append({**p, "rid": rid, "given": _typo(rng, p["given"]), "surname": _typo(rng, p["surname"]),
                          "street": _typo(rng, p["street"])})
            truth.append({"l_id": p["rid"], "r_id": rid})
    right.append({"rid": "R9999", "given": None, "surname": "orphan", "street": "", "postcode": "", "dob": ""})
    right.append({"rid": "R0000", "given": "dup", "surname": "dup", "street": "", "postcode": "", "dob": ""})  # dup id
    for name, rows in (("left", people), ("right", right), ("truth", truth)):
        with open(tmp_path / f"{name}.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)


def test_run_links_and_rejects(spark, tmp_path):
    _write(tmp_path)
    cfg = make_cfg(tmp_path,
                   inputs={"left": {"path": "left.csv", "id": "rid"}, "right": {"path": "right.csv", "id": "rid"}},
                   entity={"fields": {"given": {"type": "person_name"}, "surname": {"type": "person_name"},
                                      "street": {"type": "address"}, "postcode": {"type": "code"},
                                      "dob": {"type": "date"}}},
                   quality={"checks": [{"check": "is_not_null", "column": "given", "side": "right"}]},
                   candidates={"k": 3}, matcher={"estimator": "logistic_regression"},
                   labels={"source": "truth_sample", "n": 200},
                   evaluation={"truth": {"path": "truth.csv", "left_id": "l_id", "right_id": "r_id"}})
    summary = run(cfg, rt=Runtime(cfg, spark))
    assert summary["quarantined"] == {"left": 0, "right": 3}          # the null given name + both R0000 rows
    ev = summary["evaluation"]
    assert ev["candidate_recall"] >= 0.95
    assert ev["all"]["f1"] >= 0.9 and ev["all"]["f1"] > ev["nearest_neighbour_baseline"]["f1"]
    assert summary["paid_features_enabled"] == []
    on_disk = json.loads((tmp_path / "data" / "run_summary.json").read_text())
    assert on_disk["decision"]["links"] == summary["decision"]["links"]
    assert (tmp_path / "data" / "links").exists() and (tmp_path / "data" / "quarantine" / "right").exists()
    assert not (tmp_path / "data" / "_scratch").exists() or not any((tmp_path / "data" / "_scratch").iterdir())
