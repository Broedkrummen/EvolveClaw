"""Paired sequence reporting with family-cluster resampling."""
from collections import defaultdict
from statistics import mean
import random


METRICS = {"stale_advice": "stale_advice", "scope_leakage": "scope_leakage",
           "rollback_recurrence": "rollback_recurrence"}


def _metric_rows(records):
    future = [r for r in records if r["phase"] == "future"]
    result = {"future_task_success": {"count": sum(r["success"] for r in future),
                                      "denominator": len(future)}}
    repeats = [r for r in future if r["repeated_mistake_eligible"]]
    result["repeated_mistakes"] = {"count": sum(r["repeated_mistake"] for r in repeats),
                                  "denominator": len(repeats)}
    for name, tag in METRICS.items():
        subset = [r for r in future if tag in r["metric_tags"]]
        result[name] = {"count": sum(not r["success"] for r in subset), "denominator": len(subset)}
    for metric in result.values():
        metric["rate"] = (metric["count"] / metric["denominator"] if metric["denominator"] else None)
    return result


def paired_cluster_comparison(sequence_results, left="repaired-v0.2", right="improved", bootstrap_samples=2000, seed=71):
    """Equal-weight families; matched variants and tasks within each family.

    The interval is a descriptive harness output for scripted data. It cannot
    support an efficacy conclusion when surrogate=true.
    """
    if bootstrap_samples < 1:
        raise ValueError("bootstrap_samples must be positive")
    by_condition = defaultdict(dict)
    for row in sequence_results:
        if row["sequence_id"] in by_condition[row["condition"]]:
            raise ValueError("Duplicate matched sequence result")
        by_condition[row["condition"]][row["sequence_id"]] = row
    left_rows, right_rows = by_condition[left], by_condition[right]
    if not left_rows or left_rows.keys() != right_rows.keys():
        raise ValueError("Paired comparison requires identical nonempty sequence IDs")
    clusters = defaultdict(list)
    for sequence_id in sorted(left_rows):
        old, new = left_rows[sequence_id], right_rows[sequence_id]
        if old["cluster_id"] != new["cluster_id"]:
            raise ValueError("Matched sequence cluster IDs differ")
        old_tasks = {r["task_id"] for r in old["records"] if r["phase"] == "future"}
        new_tasks = {r["task_id"] for r in new["records"] if r["phase"] == "future"}
        if old_tasks != new_tasks or not old_tasks:
            raise ValueError("Matched sequences must contain identical nonempty future task IDs")
        clusters[old["cluster_id"]].append(new["future_success_rate"] - old["future_success_rate"])
    differences = [mean(values) for values in clusters.values()]
    rng = random.Random(seed)
    sampled = sorted(mean(rng.choices(differences, k=len(differences))) for _ in range(bootstrap_samples))
    lower = sampled[int((bootstrap_samples - 1) * .025)]
    upper = sampled[int((bootstrap_samples - 1) * .975)]
    return {"comparison": f"{right}-minus-{left}", "paired_sequences": len(left_rows),
            "family_cluster_count": len(clusters), "weighting": "equal-family-cluster",
            "future_success_rate_difference": mean(differences),
            "descriptive_cluster_bootstrap_interval_95": [lower, upper],
            "bootstrap_samples": bootstrap_samples, "seed": seed,
            "inference_warning": "Scripted mechanics only; manufactured differences are not efficacy evidence. Family labels do not establish statistical independence; the small pilot limits inference."}


def summarize(sequence_results):
    conditions = defaultdict(list)
    categories = defaultdict(lambda: defaultdict(list))
    for row in sequence_results:
        conditions[row["condition"]].extend(row["records"])
        categories[row["condition"]][row["category"]].extend(row["records"])
    summary = {"evidence_kind": "mechanics-only", "surrogate": True,
               "efficacy_evidence": False,
               "warning": "No real assistant or SCOPE learning was evaluated. All differences are scripted; no quality claim is supported.",
               "sequence_runs": len(sequence_results),
               "conditions": {condition: {"adapter": "scripted-surrogate", "surrogate": True,
                                          "evidence_kind": "mechanics-only", "metrics": _metric_rows(records),
                                          "by_category": {category: _metric_rows(rows)
                                                          for category, rows in categories[condition].items()}}
                              for condition, records in conditions.items()},
               "usage": {"model_calls": 0, "provider_tokens": {"status": "not-applicable", "input": 0, "output": 0},
                         "api_cost_usd": {"status": "actual", "amount": 0},
                         "real_evaluation_cost": {"status": "unknown", "amount": None}},
               "primary_comparison": paired_cluster_comparison(sequence_results)}
    return summary
