"""Authored task-category batches; planning/export never constructs a model."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

CATEGORIES = ("coding", "research", "writing", "planning", "data")


def role_sequences(split):
    if split not in ("diagnostic", "heldout"):
        raise ValueError("Role batches support diagnostic or heldout")
    from .coding_tasks import coding_sequences
    from .role_tasks import noncoding_sequences
    sequences = [*coding_sequences(split), *noncoding_sequences(split)]
    return sorted(sequences, key=lambda s: s.sequence_id)


def batch_manifest():
    from .scenarios import Task, validate_manifest
    rows = []
    for split in ("diagnostic", "heldout"):
        sequences = role_sequences(split)
        validate_manifest([s.manifest_entry() for s in sequences])
        for category in CATEGORIES:
            selected = [s for s in sequences if s.category == category]
            # Distribute variants across batches, instead of treating all five
            # versions of one family as five independent task families.
            selected.sort(key=lambda s: (s.sequence_id.rsplit(".", 1)[-1], s.family_id))
            expected = 10 if split == "diagnostic" else 100
            if len(selected) != expected:
                raise ValueError(f"Incomplete authored {split}/{category}: {len(selected)} != {expected}")
            for number, offset in enumerate(range(0, len(selected), 10), 1):
                group = selected[offset:offset + 10]
                rows.append({"batch_id": f"{split}.{category}.{number:02d}",
                    "split": split, "category": category, "fixture_status": "authored",
                    "sequence_ids": [s.sequence_id for s in group],
                    "sequence_count": len(group), "family_clusters": len({s.cluster_id for s in group}),
                    "task_count": sum(sum(isinstance(e, Task) for e in s.events) for s in group),
                    "future_probe_count": sum(sum(isinstance(e, Task) and e.phase == "future" for e in s.events) for s in group),
                    "five_condition_runs": len(group) * 5})
    return rows


def select_batch(batch_id, split=None):
    batch = next((row for row in batch_manifest() if row["batch_id"] == batch_id), None)
    if batch is None or (split is not None and batch["split"] != split):
        raise ValueError(f"Batch is not authored in the selected split: {batch_id}")
    return batch


def export_batches(output):
    from .scenarios import Feedback, Rollback, Task, validate_manifest
    output = Path(output).resolve()
    # Assemble and validate before creating any output, so incomplete authoring
    # cannot leave a seemingly runnable manifest.
    sequences = [*role_sequences("diagnostic"), *role_sequences("heldout")]
    validate_manifest([s.manifest_entry() for s in sequences])
    batches = batch_manifest()
    manifest = {"schema_version": 1, "status": "authored", "api_calls": 0,
        "efficacy_evidence": False, "categories": list(CATEGORIES),
        "sequence_counts": dict(Counter(s.split for s in sequences)),
        "batch_counts": dict(Counter(b["split"] for b in batches)), "batches": batches,
        "limits": ["Authored synthetic diagnostic and held-out tasks, not a published benchmark",
            "Family labels and variants do not establish independent observations",
            "Constrained Python coding tasks, not full repository/SWE-bench evaluation",
            "Writing uses explicit deterministic content constraints, not a comprehensive semantic/style judge",
            "Source snapshots are explicitly synthetic; no live-web freshness claim"]}
    public, scorer = {}, {}
    for sequence in sequences:
        events = []
        for event in sequence.events:
            if isinstance(event, Task):
                events.append({"event": "task", **event.public_request(), "phase": event.phase,
                    "tool_fixtures": [asdict(tool) for tool in event.tools]})
            elif isinstance(event, Feedback):
                events.append({"event": "feedback", **event.public_request()})
            elif isinstance(event, Rollback):
                events.append({"event": "rollback", "scope": event.scope.to_dict(), "text": event.text})
        public[sequence.sequence_id] = {**sequence.manifest_entry(), "events": events}
        scorer[sequence.sequence_id] = {k: asdict(v) for k, v in sequence.scoring_keys.items()}
    encoded = (json.dumps(public, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    manifest["public_fixture_sha256"] = sha256(encoded).hexdigest()
    manifest["scoring_keys_sha256"] = sha256(
        (json.dumps(scorer, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()).hexdigest()
    output.mkdir(parents=True, exist_ok=False)
    (output / "public").mkdir()
    (output / "scorer-only").mkdir()
    for path, value in ((output / "manifest.json", manifest),
                        (output / "public/sequences.json", public),
                        (output / "scorer-only/scoring_keys.json", scorer)):
        path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Export public fixtures and separate grader keys; no model calls")
    args = parser.parse_args(argv)
    if args.output:
        manifest = export_batches(args.output)
        print(json.dumps({"output": str(args.output.resolve()), "api_calls": 0,
            "sequence_counts": manifest["sequence_counts"], "batch_counts": manifest["batch_counts"]}))
    else:
        print(json.dumps(batch_manifest(), indent=2))


if __name__ == "__main__":
    main()
