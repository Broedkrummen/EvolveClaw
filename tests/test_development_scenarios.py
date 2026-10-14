"""Structural and public-observation reachability checks for authored fixtures."""
from collections import Counter
import json
import unittest

from evaluation.development_scenarios import development_metadata, development_sequences
from evaluation.scenarios import FakeWorld, Feedback, Rollback, Task, pilot_sequences, validate_manifest
from evaluation.scoring import score_response


def response_from_public_tools(task):
    """Independent fixture checker: no scoring key, feedback value, or future task."""
    world = FakeWorld(task)
    observations = {tool.name: world.call(tool.name, tool.arguments) for tool in task.tools}
    name = task.tools[0].name
    data = observations[name]
    if name == "time.resolve_event":
        return {"local_time": data["local_start"], "timezone": data["iana_zone"]}
    if name == "calendar.occurrence":
        return {"date": data["occurrence"]["date"], "enabled": not data["occurrence"]["cancelled"]}
    if name == "rail.connection_options":
        eligible = [r for r in data["connections"] if r["buffer_minutes"] >= data["minimum_buffer_minutes"]
                    and (not data["requires_accessibility"] or r["accessible"])]
        return {"connection_id": min(eligible, key=lambda r: r["buffer_minutes"])["id"]}
    if name == "contacts.resolve_identity":
        records = [r for r in data["records"] if r["person"] == data["requested_person"]
                   and r["organization"] == data["requested_organization"] and r["active"]]
        return {"email": records[0]["email"]}
    if name == "mail.thread_members":
        return {"recipients": sorted(r["id"] for r in data["members"] if r["active"] and r["notifications"])}
    if name == "documents.release_revisions":
        record = max((r for r in data["revisions"] if r["approved"] and r["document"] == data["requested_document"]),
                     key=lambda r: r["revision"])
        return {"file_id": record["file_id"], "revision": record["revision"]}
    if name == "expenses.normalized_entries":
        return {"total_cents": sum(r["converted_minor"] for r in data["entries"]), "currency": data["report_currency"]}
    if name == "research.first_page":
        if data["next_cursor"] != task.tools[1].arguments["cursor"]:
            raise AssertionError("Next-page arguments cannot reach the returned cursor")
        second = observations["research.next_page"]
        if second["next_cursor"] is not None:
            raise AssertionError("A missing advertised page makes this fixture incomplete")
        return {"count": len(data["items"]) + len(second["items"])}
    if name == "meetings.summary_consent":
        return {"included": sorted(r["id"] for r in data["participants"] if r["consented_to_summary"])}
    if name == "catalog.normalized_dimensions":
        record = max((r for r in data["products"] if r["width_mm"] <= data["available_width_mm"]),
                     key=lambda r: r["width_mm"])
        return {"sku": record["sku"]}
    if name == "subscriptions.entitlement":
        return {"renews": data["auto_renew"] and not data["cancel_at_period_end"], "access_until": data["access_until"]}
    if name == "credits.eligible_lines":
        eligible = [r for r in data["lines"] if r["eligible"]]
        return {"credit_cents": sum(r["amount_cents"] for r in eligible), "eligible_ids": sorted(r["id"] for r in eligible)}
    if name == "documents.comparison_changes":
        return {"fields": sorted(r["field"] for r in data["changes"] if r["approved"]
                and r["from_version"] == data["from_version"] and r["to_version"] == data["to_version"])}
    if name == "notifications.delivery_policy":
        defer = data["quiet_now"] and not (data["urgent"] and data["urgent_bypass_allowed"])
        return {"deliver_at": data["next_allowed_local"] if defer else data["now_local"]}
    if name == "devices.adapter_requirements":
        required = data["required"]
        record = next(r for r in data["adapters"] if r["connector"] == required["connector"]
                      and r["voltage"] == required["voltage"] and r["watts"] >= required["minimum_watts"])
        return {"adapter_id": record["id"]}
    if name == "sharing.project_policy":
        return dict(data["project_policy"])
    if name == "recipes.serving_request":
        scale = data["target_servings"] / data["base_servings"]
        return {"flour_g": int(data["ingredients_grams"]["flour"] * scale),
                "water_g": int(data["ingredients_grams"]["water"] * scale)}
    if name == "assets.publication_license":
        return {"allowed": data["authoritative_license"]["commercial_use_allowed"],
                "attribution": data["authoritative_license"]["attribution_required"]}
    if name == "downloads.content_checks":
        record = next(r for r in data["downloads"] if r["signature_verified"] and r["verified_type"] == data["requested_type"])
        return {"filename": record["name"]}
    if name == "availability.group_windows":
        required = set(data["required_members"])
        record = min((r for r in data["candidates"] if r["minutes"] >= data["duration_minutes"]
                      and required.issubset(r["available_members"])), key=lambda r: r["start"])
        return {"start": record["start"]}
    raise AssertionError(f"Uncovered public fixture tool: {name}")


class DevelopmentFixtureTests(unittest.TestCase):
    def test_authored_counts_and_clustered_variants_are_explicit(self):
        sequences = development_sequences()
        self.assertIsInstance(sequences, tuple)
        self.assertEqual(len(sequences), 100)
        counts = Counter(s.family_id for s in sequences)
        self.assertEqual(len(counts), 20)
        self.assertEqual(set(counts.values()), {5})
        self.assertTrue(all(s.cluster_id == s.family_id and s.split == "development" for s in sequences))
        metadata = development_metadata()
        self.assertEqual(metadata["cluster_count"], 20)
        self.assertEqual(metadata["future_probe_count"], 200)
        self.assertFalse(metadata["published_benchmark"])
        self.assertIn("not 100 independent", metadata["independence_note"])

    def test_all_ids_keys_and_tool_contracts_are_unique_complete_and_reachable(self):
        sequences = development_sequences()
        self.assertEqual(len({s.sequence_id for s in sequences}), 100)
        task_ids, tool_names = set(), set()
        for sequence in sequences:
            tasks = [event for event in sequence.events if isinstance(event, Task)]
            self.assertEqual(len(tasks), 3)
            self.assertEqual([t.phase for t in tasks], ["learning", "future", "future"])
            self.assertIsInstance(sequence.events[1], Feedback)
            self.assertEqual(set(sequence.scoring_keys), {t.task_id for t in tasks})
            for task in tasks:
                self.assertNotIn(task.task_id, task_ids)
                task_ids.add(task.task_id)
                self.assertTrue(task.instruction.strip())
                self.assertEqual(len({t.name for t in task.tools}), len(task.tools))
                key = sequence.scoring_keys[task.task_id]
                self.assertTrue(key.required_fields)
                for field in key.required_fields:
                    self.assertIn(field, task.instruction)
                json.dumps(task.public_request(), allow_nan=False)
                answer = response_from_public_tools(task)
                self.assertTrue(score_response(answer, key)["success"], (task.task_id, answer, key.required_fields))
                # Every fixture uses strict advertised arguments and detached results.
                world = FakeWorld(task)
                for tool in task.tools:
                    tool_names.add(tool.name)
                    original = json.dumps(tool.result, sort_keys=True)
                    result = world.call(tool.name, tool.arguments)
                    result["test_local_mutation"] = True
                    self.assertEqual(json.dumps(tool.result, sort_keys=True), original)
                    with self.assertRaises(ValueError):
                        world.call(tool.name, {"unadvertised": True})
        self.assertEqual(len(task_ids), 300)
        self.assertEqual(len(tool_names), 21)

    def test_public_requests_do_not_contain_keys_or_tool_results(self):
        forbidden = {"scoring_keys", "required_fields", "metric_tags", "mistake_key", "expected", "gold", "result"}

        def inspect(value):
            if isinstance(value, dict):
                self.assertFalse(forbidden.intersection(value))
                for child in value.values():
                    inspect(child)
            elif isinstance(value, list):
                for child in value:
                    inspect(child)

        for sequence in development_sequences():
            for event in sequence.events:
                if isinstance(event, (Task, Feedback)):
                    inspect(event.public_request())
                if isinstance(event, Feedback):
                    self.assertIsNone(event.value)
                    self.assertTrue(event.text.strip())

    def test_pilot_disjointness_and_manifest_admission(self):
        development, pilot = development_sequences(), pilot_sequences()
        self.assertFalse({s.family_id for s in development}.intersection(s.family_id for s in pilot))
        self.assertFalse({s.cluster_id for s in development}.intersection(s.cluster_id for s in pilot))
        self.assertFalse({s.events[0].topic for s in development}.intersection(s.events[0].topic for s in pilot))
        pilot_tools = {t.name for s in pilot for e in s.events if isinstance(e, Task) for t in e.tools}
        dev_tools = {t.name for s in development for e in s.events if isinstance(e, Task) for t in e.tools}
        self.assertFalse(dev_tools.intersection(pilot_tools))
        rows = [s.manifest_entry() for s in (*pilot, *development)]
        validate_manifest(rows)
        self.assertTrue(all(s.manifest_entry()["fixture_status"] == "authored" for s in development))

    def test_fresh_scope_source_and_undo_cases_exist_without_manufactured_keys(self):
        scope_switches = rollback_sequences = 0
        untrusted = 0
        for sequence in development_sequences():
            tasks = [e for e in sequence.events if isinstance(e, Task)]
            if tasks[0].scope != tasks[2].scope:
                scope_switches += 1
                self.assertIn("scope_leakage", sequence.scoring_keys[tasks[2].task_id].metric_tags)
            if any(isinstance(e, Rollback) for e in sequence.events):
                rollback_sequences += 1
                self.assertIn("rollback_recurrence", sequence.scoring_keys[tasks[2].task_id].metric_tags)
                self.assertIsInstance(sequence.events[-2], Rollback)
            for task in tasks:
                if "untrusted_" in json.dumps([t.result for t in task.tools]):
                    untrusted += 1
            # Probes are genuinely fresh observations, not repeats of the same task IDs/results.
            self.assertNotEqual(tasks[0].task_id, tasks[1].task_id)
            self.assertNotEqual(tasks[1].tools[0].result, tasks[2].tools[0].result)
        self.assertEqual(scope_switches, 30)
        self.assertEqual(rollback_sequences, 10)
        self.assertGreaterEqual(untrusted, 45)


if __name__ == "__main__":
    unittest.main()
