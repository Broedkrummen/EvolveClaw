import concurrent.futures
import json

import pytest

from memory_store import MemoryStore, RevisionConflict

A = {"audience_key": "owner:one", "project_key": "A"}
B = {"audience_key": "owner:one", "project_key": "B"}
OTHER = {"audience_key": "owner:two", "project_key": "A"}


def add(store, text="Validate the input schema", scope=A, **kwargs):
    return store.add_rule("agent", scope, text, expected_revision=store.revision("agent", scope), **kwargs)


def mutate(store, operation, args=None, scope=A, **kwargs):
    return store.mutate("agent", scope, operation, args or {}, store.revision("agent", scope), **kwargs)


def test_scoped_persistence_and_unknown_scope(tmp_path):
    store = MemoryStore(tmp_path)
    rule = add(store)
    reopened = MemoryStore(tmp_path)
    assert reopened.active_rules("agent", A)[0]["id"] == rule["id"]
    assert reopened.active_rules("agent", B) == []
    assert reopened.active_rules("agent", OTHER) == []
    assert reopened.active_rules("another-agent", A) == []
    with pytest.raises(ValueError):
        reopened.query("agent", None)
    with pytest.raises(KeyError):
        reopened.query("agent", OTHER, "detail", {"rule_id": rule["id"]})


def test_opposite_instructions_are_not_lexical_duplicates(tmp_path):
    store = MemoryStore(tmp_path)
    add(store, "Always use the browser tool for all research tasks")
    assert add(store, "Never use the browser tool for all research tasks")
    assert add(store, "Never use the browser tool for all research tasks") is None
    assert len(store.active_rules("agent", A)) == 2


def test_disable_undo_and_stale_revision_are_atomic(tmp_path):
    store = MemoryStore(tmp_path)
    rule = add(store)
    snapshot = mutate(store, "disable", {"rule_id": rule["id"]})
    disable_id = snapshot["history"][0]["id"]
    assert store.active_rules("agent", A) == []
    assert add(store) is None  # Learning cannot silently reactivate disabled guidance.
    with pytest.raises(RevisionConflict):
        store.mutate("agent", A, "restore", {"rule_id": rule["id"]}, 1)
    assert store.query("agent", A)["revision"] == 2
    new = add(store, "Track verified source references")
    restored = mutate(store, "restore", {"history_id": disable_id})
    assert {r["id"] for r in store.active_rules("agent", A)} == {rule["id"], new["id"]}
    assert restored["revision"] == 4
    assert all("before" not in h and "after" not in h for h in restored["history"])


def test_legacy_import_is_once_inactive_reversible_and_owner_only(tmp_path):
    path = tmp_path / "strategic_memory" / "global_rules.json"
    path.parent.mkdir()
    original = json.dumps({"agent": {"general": [{"rule": "Legacy advice", "confidence": .9}]}})
    path.write_text(original)
    store = MemoryStore(tmp_path)
    assert store.active_rules("agent", A) == []
    with pytest.raises(PermissionError):
        store.query("agent", A, args={"include_legacy": True})
    legacy = store.query("agent", A, args={"include_legacy": True}, authorize_legacy=True)["rules"][0]
    with pytest.raises(PermissionError):
        mutate(store, "assign_scope", {"rule_id": legacy["id"]})
    with pytest.raises(ValueError):
        mutate(store, "restore", {"rule_id": legacy["id"]}, authorize_legacy=True)
    assigned = mutate(store, "assign_scope", {"rule_id": legacy["id"], "target_scope": A}, authorize_legacy=True)
    assignment = assigned["history"][0]["id"]
    assert store.active_rules("agent", A)[0]["text"] == "Legacy advice"
    mutate(store, "restore", {"history_id": assignment})
    assert store.active_rules("agent", A) == []
    assert path.read_text() == original
    reopened = MemoryStore(tmp_path)
    assert len(reopened.query("agent", A, args={"include_legacy": True}, authorize_legacy=True)["rules"]) == 1


def test_scope_and_owner_assignment_cannot_cross_audiences(tmp_path):
    path = tmp_path / "strategic_memory" / "global_rules.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"agent": {"general": [{"rule": "Old", "confidence": .9}]}}))
    store = MemoryStore(tmp_path)
    legacy = store.query("agent", A, args={"include_legacy": True}, authorize_legacy=True)["rules"][0]
    with pytest.raises(PermissionError):
        mutate(store, "assign_scope", {"rule_id": legacy["id"], "target_scope": OTHER}, authorize_legacy=True)
    assert store.revision("agent", A) == 0


def test_concurrent_checked_writes_and_slow_compaction_keep_all_new_advice(tmp_path):
    store = MemoryStore(tmp_path)
    def competing(text):
        try:
            return store.add_rule("agent", A, text, expected_revision=0)
        except RevisionConflict:
            return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(competing, ("First proposed rule", "Second proposed rule")))
    assert sum(r is not None for r in results) == 1
    base_revision, snapshot = store.domain_snapshot("agent", A, "general")
    new_rule = add(store, "Concurrent accepted rule")
    with pytest.raises(RevisionConflict):
        store.consolidate("agent", A, "general", [{"rule": "Old compacted snapshot", "confidence": .9}], base_revision)
    assert new_rule["id"] in {r["id"] for r in store.active_rules("agent", A)}
    assert len(store.active_rules("agent", A)) == 2


def test_consolidation_keeps_evidence_and_can_be_undone(tmp_path):
    store = MemoryStore(tmp_path, max_rules_per_domain=2)
    evidence = store.record_evidence("agent", A, "task", {"error": "schema mismatch"})
    first = add(store, "Check required fields", evidence_id=evidence["id"])
    second = add(store, "Check data types")
    revision, _ = store.domain_snapshot("agent", A, "general")
    store.consolidate("agent", A, "general", [{"rule": "Validate schemas", "confidence": .9}], revision)
    merged = store.active_rules("agent", A)[0]
    assert merged["evidence_ids"] == [evidence["id"]]
    assert set(merged["parent_ids"]) == {first["id"], second["id"]}
    change = store.query("agent", A)["history"][0]
    mutate(store, "restore", {"history_id": change["id"]})
    assert {r["id"] for r in store.active_rules("agent", A)} == {first["id"], second["id"]}


def test_pause_is_scoped_and_controls_are_reversible(tmp_path):
    store = MemoryStore(tmp_path)
    paused = mutate(store, "pause")
    assert store.paused("agent", A)
    assert not store.paused("agent", B)
    assert add(store) is None
    assert add(store, scope=B)
    undone = mutate(store, "restore", {"history_id": paused["history"][0]["id"]})
    assert not store.paused("agent", A)
    mutate(store, "restore", {"history_id": undone["history"][0]["id"]})
    assert store.paused("agent", A)


def test_tactical_reset_does_not_expire_another_scope_or_strategic_rule(tmp_path):
    store = MemoryStore(tmp_path)
    persistent = add(store, "Reusable guidance")
    add(store, "Temporary A", type="tactical", task_id="same")
    other = add(store, "Temporary B", scope=B, type="tactical", task_id="same")
    store.reset_tactical("agent", A, "same")
    assert [r["id"] for r in store.active_rules("agent", A, "same")] == [persistent["id"]]
    assert other["id"] in {r["id"] for r in store.active_rules("agent", B, "same")}


def test_unknown_usage_and_run_success_do_not_invent_quality_or_free_cost(tmp_path):
    store = MemoryStore(tmp_path)
    store.record_usage("agent", A, "synthesis")
    store.record_usage("agent", A, "classification", "actual", 80, 20)
    store.record_usage("agent", A, "consolidation", "estimated", 60, 30)
    usage = store.query("agent", A, "usage")["usage"]
    assert usage["calls"] == 3
    assert usage["unknown"]["calls"] == 1
    assert usage["actual"]["input_tokens"] == 80
    assert usage["estimated"]["output_tokens"] == 30
    assert usage["cost"] == {"status": "unknown", "amount": None, "currency": "USD"}
    assert store.query("agent", OTHER)["usage"]["calls"] == 0
    outcome = store.record_outcome("agent", A, "task", "success", "agent_run")
    assert outcome["result"] == "unknown"
    assert not outcome["validated"]


def test_promotion_requires_validated_distinct_projects_inside_audience(tmp_path):
    store = MemoryStore(tmp_path)
    rules = []
    for scope in (A, B):
        evidence = store.record_evidence("agent", scope, "task", {"observation": "verified fixture"})
        rules.append(add(store, scope=scope, evidence_id=evidence["id"]))
        store.record_outcome("agent", scope, "task", "success", "agent_run", evidence["id"], [rules[-1]["id"]])
    with pytest.raises(RevisionConflict):
        mutate(store, "promote", {"rule_id": rules[0]["id"]})
    for scope, rule in zip((A, B), rules):
        store.record_outcome("agent", scope, "task", "success", "fixture", rule["evidence_ids"][0], [rule["id"]])
    mutate(store, "promote", {"rule_id": rules[0]["id"]})
    project_c = {**A, "project_key": "C"}
    assert store.active_rules("agent", project_c)[0]["id"] == rules[0]["id"]
    assert store.active_rules("agent", OTHER) == []
    detail = store.query("agent", project_c, "detail", {"rule_id": rules[0]["id"]})["detail"]
    assert detail["evidence"] == []
    assert detail["rule"]["evidence_ids"] == []
