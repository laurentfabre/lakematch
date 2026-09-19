"""Anchor/record-group bootstrap and deterministic validation-only selection."""
import math
import random

BOOTSTRAP_SEED = 2026091902


def counts(tp, fp, fn, tn=0):
    precision = tp / (tp + fp) if tp + fp else 0.
    recall = tp / (tp + fn) if tp + fn else 0.
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": precision, "recall": recall, "f1": f1}


def select(rows, threshold, cardinality):
    # Matches decision.links ordering, including its conservative no-reassignment policy.
    kept = {}
    for a, b, probability in rows:
        if math.isfinite(probability) and probability >= threshold:
            kept[a, b] = max(probability, kept.get((a, b), -math.inf))
    ranked = sorted(((a, b, p) for (a, b), p in kept.items()), key=lambda row: (-row[2], row[0], row[1]))
    if cardinality in {"one_to_one", "many_to_one"}:
        anchors, ranked_a = set(), []
        for a, b, p in ranked:
            if a not in anchors:
                anchors.add(a)
                ranked_a.append((a, b, p))
        ranked = ranked_a
    if cardinality == "one_to_one":
        partners, ranked_b = set(), []
        for a, b, p in ranked:
            if b not in partners:
                partners.add(b)
                ranked_b.append((a, b, p))
        ranked = ranked_b
    return {(a, b) for a, b, _ in ranked}


def evaluate(predictions, labels, groups):
    """labels includes every evaluated pair; omitted true links must still be present."""
    unknown = predictions - labels.keys()
    if unknown:
        raise ValueError("Predictions include unlabeled pairs; cannot assume negatives")
    totals = {}
    for pair, truth in labels.items():
        group = groups[pair]
        bucket = totals.setdefault(group, [0, 0, 0, 0])
        predicted = pair in predictions
        index = 0 if truth and predicted else 1 if predicted else 2 if truth else 3
        bucket[index] += 1
    combined = [sum(row[i] for row in totals.values()) for i in range(4)]
    return counts(*combined), totals


def tune(rows, labels, groups, cardinality):
    # Frozen finite grid, ties choose the higher threshold (fewer positive decisions).
    grid = [i / 100 for i in range(101)]
    ranked = []
    for threshold in grid:
        result, _ = evaluate(select(rows, threshold, cardinality), labels, groups)
        ranked.append((result["f1"], threshold))
    return max(ranked)[1]


def bootstrap(totals, reference=None, resamples=2000):
    keys = sorted(totals)
    if not keys:
        raise ValueError("Cannot bootstrap an empty evaluation")
    if reference is not None and set(reference) != set(keys):
        raise ValueError("Paired bootstrap requires identical groups")
    rng = random.Random(BOOTSTRAP_SEED)
    values, differences = [], []
    for _ in range(resamples):
        chosen = rng.choices(keys, k=len(keys))
        row = [sum(totals[g][i] for g in chosen) for i in range(3)]
        score = counts(*row)["f1"]
        values.append(score)
        if reference is not None:
            base = [sum(reference[g][i] for g in chosen) for i in range(3)]
            differences.append(score - counts(*base)["f1"])
    def interval(values):
        ordered = sorted(values)
        return [ordered[int((len(ordered) - 1) * .025)], ordered[int((len(ordered) - 1) * .975)]]
    return {"f1_95ci": interval(values), "paired_delta_95ci": interval(differences) if reference is not None else None,
            "seed": BOOTSTRAP_SEED, "resamples": resamples, "groups": len(keys)}
