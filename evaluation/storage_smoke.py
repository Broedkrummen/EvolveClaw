"""Mechanical integration against the actual production MemoryStore.

No SCOPE/model synthesis is called. Explicit authored lessons only exercise
storage, evidence links, isolation, revision checks, outcome provenance, and undo.
"""
import importlib.util
from pathlib import Path


def load_memory_store():
    path = Path(__file__).resolve().parents[1] / "server" / "memory_store.py"
    spec = importlib.util.spec_from_file_location("evaluation_actual_memory_store", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_storage_smoke(directory: Path):
    directory = directory.resolve()
    if directory.exists():
        raise FileExistsError("Choose a new isolated storage-smoke directory")
    module = load_memory_store()
    store = module.MemoryStore(directory)
    agent = "simulated-agent"
    scope = {"audience_key": "sim:user-a", "project_key": "sim:project-a"}
    other_user = {**scope, "audience_key": "sim:user-b"}
    other_project = {**scope, "project_key": "sim:project-b"}
    evidence = store.record_evidence(agent, scope, "calendar-learning",
                                     "Fake calendar returned status=failed; user corrected the completion claim.")
    rule = store.add_rule(agent, scope, "Check tool status before claiming completion.",
                          task_id="calendar-learning", evidence_id=evidence["id"],
                          expected_revision=store.revision(agent, scope))
    assert rule is not None
    assert len(store.active_rules(agent, scope)) == 1
    assert store.active_rules(agent, other_user) == []
    assert store.active_rules(agent, other_project) == []
    snapshot = store.query(agent, scope)
    learn_history = next(h for h in snapshot["history"] if h["operation"] == "learn")
    outcome = store.record_outcome(agent, scope, "calendar-followup", "success", "fixture",
                                   evidence_id=evidence["id"], rule_ids=[rule["id"]],
                                   details={"simulated": True})
    assert outcome["validated"] and outcome["result"] == "success"
    uncertain = store.record_outcome(agent, scope, "unverified-run", "success", "agent_run")
    assert not uncertain["validated"] and uncertain["result"] == "unknown"
    try:
        store.mutate(agent, other_user, "disable", {"rule_id": rule["id"]},
                     expected_revision=store.revision(agent, other_user))
    except KeyError:
        pass
    else:
        raise AssertionError("Cross-user mutation should be rejected")
    store.mutate(agent, scope, "restore", {"history_id": learn_history["id"]},
                 expected_revision=store.revision(agent, scope))
    assert store.active_rules(agent, scope) == []
    restored = module.MemoryStore(directory)
    assert restored.active_rules(agent, scope) == []
    try:
        restored.add_rule(agent, scope, "A stale write must not be accepted.", expected_revision=0)
    except module.RevisionConflict:
        pass
    else:
        raise AssertionError("Stale revision was accepted")
    return {"evidence_kind": "mechanics-only", "actual_memory_store": True,
            "scripted_assistant": False, "model_calls": 0, "efficacy_evidence": False,
            "checks": ["evidence-link", "user-isolation", "project-isolation", "scope-mutation-rejection",
                       "fixture-outcome-provenance", "agent-success-is-unknown", "history-undo",
                       "persistent-undo", "stale-write-rejection"]}
