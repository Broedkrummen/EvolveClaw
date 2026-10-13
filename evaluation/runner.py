"""Local pilot runner. Independent scorer keys are never agent inputs."""
from dataclasses import asdict
from pathlib import Path
from statistics import mean
from time import perf_counter
import json

from .adapters import CONDITIONS, ScriptedAssistant, ScriptedMemory
from .reporting import summarize
from .scenarios import Task, Feedback, Rollback, FakeWorld, pilot_sequences, planned_manifest, validate_manifest
from .scoring import score_response


def _write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def run_sequence(sequence, condition, directory):
    memory = ScriptedMemory(condition, directory / "memory")
    assistant = ScriptedAssistant(memory)
    public_events, trace, records = [], [], []
    failed_before = set()
    corrected = set()
    for event in sequence.events:
        if isinstance(event, Task):
            public_request = {"event": "task", **event.public_request()}
            public_events.append(public_request)
            world = FakeWorld(event)
            started = perf_counter()
            response = assistant.run_task(event, world)
            elapsed = perf_counter() - started
            key = sequence.scoring_keys[event.task_id]
            score = score_response(response, key)
            mistake_context = (event.scope.audience_key, event.scope.project_key, key.mistake_key)
            eligible = mistake_context in failed_before and mistake_context in corrected
            repeated = bool(eligible and not score["success"])
            records.append({"task_id": event.task_id, "phase": event.phase, **score,
                            "repeated_mistake_eligible": eligible, "repeated_mistake": repeated,
                            "scripted_elapsed_seconds": elapsed})
            if not score["success"] and key.mistake_key:
                failed_before.add(mistake_context)
            trace.append({"event": "task", "request": public_request, "tool_calls": world.calls,
                          "response": response, "scoring": records[-1]})
        elif isinstance(event, Feedback):
            request = {"event": "feedback", **event.public_request()}
            public_events.append(request)
            corrected.add((event.scope.audience_key, event.scope.project_key, event.topic))
            trace.append({"event": "feedback", "request": request, "memory": memory.feedback(event)})
        elif isinstance(event, Rollback):
            request = {"event": "rollback", "scope": event.scope.to_dict(), "text": event.text}
            public_events.append(request)
            trace.append({"event": "rollback", "request": request, "memory": memory.rollback(event.scope)})
    _write_json(directory / "public_requests.json", public_events)
    _write_json(directory / "scored_trace.json", trace)
    future = [record["success"] for record in records if record["phase"] == "future"]
    return {"sequence_id": sequence.sequence_id, "family_id": sequence.family_id,
            "cluster_id": sequence.cluster_id, "category": sequence.category, "split": sequence.split,
            "condition": condition, "adapter": "scripted-surrogate", "surrogate": True,
            "evidence_kind": "mechanics-only", "future_success_rate": mean(future), "records": records}


def run_pilot(output: Path):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    sequences = pilot_sequences()
    manifest = planned_manifest()
    validate_manifest(manifest)
    _write_json(output / "manifest.json", {"schema_version": 1, "sequences": manifest})
    scorer_dir = output / "scorer-only"
    scorer_dir.mkdir()
    _write_json(scorer_dir / "scoring_keys.json", {sequence.sequence_id: {
        task_id: asdict(key) for task_id, key in sequence.scoring_keys.items()} for sequence in sequences})
    results = []
    for condition in CONDITIONS:
        for sequence in sequences:
            directory = output / condition / sequence.sequence_id
            directory.mkdir(parents=True)
            results.append(run_sequence(sequence, condition, directory))
    summary = summarize(results)
    summary.update({"authored_sequences": len(sequences), "family_clusters": len({s.cluster_id for s in sequences}),
                    "future_tasks_per_condition": sum(sum(isinstance(e, Task) and e.phase == "future" for e in s.events) for s in sequences),
                    "planned_development_sequences": 100, "planned_heldout_sequences": 500,
                    "planned_fixtures_warning": "Development and held-out rows reserve authoring slots; no runnable fixtures or evidence yet."})
    _write_json(output / "sequence_results.json", results)
    _write_json(output / "summary.json", summary)
    (output / "README.txt").write_text("MECHANICS ONLY: scripted surrogates, not real AI versions.\n"
                                       "Scorer keys and scored traces must be outside any real agent's filesystem sandbox.\n"
                                       "No model/network calls; real evaluation usage and cost remain unknown.\n")
    return summary
