"""Offline fixture reachability; these checks establish no model efficacy."""
from collections import Counter
from copy import deepcopy
from dataclasses import replace
import inspect
import json
import re
import unittest
from unittest.mock import patch

from evaluation import role_tasks
from evaluation.development_scenarios import development_sequences
from evaluation.role_tasks import FAMILIES, noncoding_metadata, noncoding_response, noncoding_sequences
from evaluation.scenarios import FakeWorld, Feedback, Task, pilot_sequences
from evaluation.scoring import score_response


class RoleTasksTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.diagnostic = noncoding_sequences("diagnostic")
        cls.heldout = noncoding_sequences("heldout")
        cls.all_sequences = cls.diagnostic + cls.heldout

    def test_counts_categories_families_and_two_warmups_before_feedback(self):
        for split, sequences, count, families, variants in (
                ("diagnostic", self.diagnostic, 40, 20, 2),
                ("heldout", self.heldout, 400, 80, 5)):
            self.assertEqual(len(sequences), count)
            self.assertEqual(len({sequence.cluster_id for sequence in sequences}), families)
            self.assertEqual(Counter(s.category for s in sequences),
                             {category: count // 4 for category in ("research", "writing", "planning", "data")})
            self.assertEqual(set(Counter(s.family_id for s in sequences).values()), {variants})
            for sequence in sequences:
                self.assertEqual(sequence.split, split)
                self.assertEqual(sequence.family_id, sequence.cluster_id)
                self.assertRegex(sequence.sequence_id, rf"^{split}\.(research|writing|planning|data)\.[a-z-]+\.\d{{2}}$")
                self.assertEqual([type(event) for event in sequence.events], [Task, Task, Feedback, Task, Task])
                tasks = [event for event in sequence.events if isinstance(event, Task)]
                self.assertEqual([task.phase for task in tasks], ["learning", "learning", "future", "future"])
                self.assertEqual(set(sequence.scoring_keys), {task.task_id for task in tasks})
                self.assertTrue(sequence.events[2].text.startswith("For the next fresh tasks, remember this procedure:"))
        self.assertEqual(noncoding_metadata("heldout")["scored_tasks"], 1600)
        self.assertEqual(noncoding_metadata("diagnostic")["future_probes"], 80)
        for invalid in ("pilot", "development", "", None):
            with self.assertRaises(ValueError):
                noncoding_sequences(invalid)

    def test_split_identity_and_raw_mechanism_shapes_are_distinct(self):
        groups = [self.diagnostic, self.heldout, pilot_sequences(), development_sequences()]
        for index, left in enumerate(groups):
            for right in groups[index + 1:]:
                for field in ("sequence_id", "family_id", "cluster_id"):
                    self.assertFalse({getattr(s, field) for s in left} & {getattr(s, field) for s in right})
        self.assertEqual(len(FAMILIES), 100)
        self.assertEqual(len({family.lesson for family in FAMILIES}), 100)
        for category in ("research", "writing", "planning", "data"):
            families = [family for family in FAMILIES if family.category == category]
            self.assertEqual(len(families), 25)
            # Structural distinction is necessary, not evidence of independence
            # or sufficient model difficulty. No family is an ID-only rename.
            schemas = []
            def structure(value):
                if isinstance(value, dict):
                    return tuple((key, structure(child)) for key, child in sorted(value.items()))
                if isinstance(value, list):
                    return ("list", tuple(sorted({repr(structure(child)) for child in value})))
                return type(value).__name__
            for family in families:
                sequence = next(s for s in self.all_sequences if s.category == category
                                and s.sequence_id.split(".")[2] == family.name)
                task = sequence.events[0]
                data = next(tool.result["data"] for tool in task.tools if "data" in tool.result)
                schemas.append(structure(data))
            self.assertEqual(len(set(schemas)), 25)

    def test_every_family_has_fresh_actual_public_data_for_each_task_state(self):
        by_family = {}
        def without_record_ids(value):
            if isinstance(value, dict):
                return {key: without_record_ids(child) for key, child in value.items()
                        if key != "id" and not key.endswith("_id")}
            if isinstance(value, list):
                return [without_record_ids(child) for child in value]
            return value
        for sequence in self.all_sequences:
            hashes = by_family.setdefault(sequence.family_id, set())
            for task in sequence.events:
                if not isinstance(task, Task):
                    continue
                data = next(tool.result["data"] for tool in task.tools if "data" in tool.result)
                fingerprint = json.dumps(without_record_ids(data), sort_keys=True)
                self.assertNotIn(fingerprint, hashes, task.task_id)
                hashes.add(fingerprint)

    def test_every_one_of_1760_task_states_has_a_public_observation_answer(self):
        count = writing = 0
        for sequence in self.all_sequences:
            for task in sequence.events:
                if not isinstance(task, Task):
                    continue
                count += 1
                response = noncoding_response(task)
                key = sequence.scoring_keys[task.task_id]
                self.assertTrue(score_response(response, key)["success"], task.task_id)
                self.assertIn("return", task.instruction.casefold())
                if sequence.category == "writing":
                    writing += 1
                    self.assertIsInstance(response["text"], str)
                    self.assertIsInstance(response["facts"], dict)
                    self.assertEqual(key.grading["kind"], "writing")
                    self.assertIn("at most 45 words", task.instruction)
                    for phrase_group in key.grading["required_phrases"]:
                        self.assertTrue(all(phrase in task.instruction for phrase in phrase_group))
                    self.assertTrue(all(phrase in task.instruction for phrase in key.grading["forbidden_phrases"]))
        self.assertEqual(count, 1760)
        self.assertEqual(writing, 440)

    def test_keys_never_enter_tool_results_or_public_requests(self):
        forbidden = {"answer", "expected", "expected_response", "required_fields", "grading",
                     "scoring_keys", "metric_tags", "mistake_key"}
        def walk(value):
            if isinstance(value, dict):
                self.assertFalse(forbidden & value.keys())
                for child in value.values():
                    walk(child)
            elif isinstance(value, (list, tuple)):
                for child in value:
                    walk(child)
        for sequence in self.all_sequences:
            for event in sequence.events:
                public = event.public_request()
                walk(public)
                for marker in ("required_fields", "scoring_keys", "mistake_key", "required_phrases"):
                    self.assertNotIn(marker, json.dumps(public))
                if isinstance(event, Task):
                    for tool in event.tools:
                        walk(tool.result)
                    bundle = next(tool.result for tool in event.tools if "data" in tool.result)
                    self.assertIn("Explicitly synthetic fictional fixture", bundle["notice"])
                    self.assertTrue(bundle["source_id"].startswith("synthetic:"))
                    self.assertEqual(bundle["scope"], event.scope.to_dict())

    def test_oracle_does_not_consult_constructor_keys_and_changes_with_public_data(self):
        tasks = [next(s for s in self.diagnostic if s.category == category).events[0]
                 for category in ("research", "writing", "planning", "data")]
        with patch.object(role_tasks, "_research", side_effect=AssertionError("No private builder")), \
             patch.object(role_tasks, "_writing", side_effect=AssertionError("No private builder")), \
             patch.object(role_tasks, "_planning", side_effect=AssertionError("No private builder")), \
             patch.object(role_tasks, "_data", side_effect=AssertionError("No private builder")):
            for task in tasks:
                self.assertTrue(noncoding_response(task))
        source = inspect.getsource(noncoding_response)
        for private in ("scoring_keys", "required_fields", "score_response", "_sequence("):
            self.assertNotIn(private, source)
        task = next(s for s in self.diagnostic if ".evidence-window." in s.sequence_id).events[0]
        tools = deepcopy(task.tools)
        tools[0].result["data"]["sources"][1]["value"] = 777
        changed = replace(task, tools=tools)
        self.assertEqual(noncoding_response(changed)["value"], 777)
        self.assertNotEqual(noncoding_response(task)["value"], 777)

    def test_fixtures_are_isolated_exact_argument_calls_with_recovery_and_scope_cases(self):
        scope_switches = recovery_sequences = 0
        for sequence in self.all_sequences:
            tasks = [event for event in sequence.events if isinstance(event, Task)]
            if tasks[-1].scope != tasks[0].scope:
                scope_switches += 1
                self.assertEqual(tasks[-1].scope.audience_key, tasks[0].scope.audience_key)
                self.assertNotEqual(tasks[-1].scope.project_key, tasks[0].scope.project_key)
            if any(tool.result.get("status") == "failed" for tool in tasks[0].tools):
                recovery_sequences += 1
            task = tasks[0]
            world = FakeWorld(task)
            tool = next(tool for tool in task.tools if "data" in tool.result)
            observed = world.call(tool.name, tool.arguments)
            observed["data"].clear()
            self.assertTrue(world.call(tool.name, tool.arguments)["data"])
            with self.assertRaises(ValueError):
                world.call(tool.name, {"record": "wrong"})
            with self.assertRaises(ValueError):
                world.call("live.account.operation", {})
        self.assertEqual(scope_switches, 88)
        self.assertEqual(recovery_sequences, 88)

    def test_writing_rubric_rejects_missing_text_word_overrun_false_facts_and_forbidden_content(self):
        for sequence in self.all_sequences:
            if sequence.category != "writing":
                continue
            task = sequence.events[0]
            key = sequence.scoring_keys[task.task_id]
            response = noncoding_response(task)
            for bad in ({"facts": response["facts"]},
                        {**response, "text": response["text"] + " " + "word " * 60},
                        {**response, "facts": {}},
                        {**response, "text": response["text"] + " " + key.grading["forbidden_phrases"][0]}):
                self.assertFalse(score_response(bad, key)["success"], task.task_id)

    def test_numeric_writing_phrases_are_not_substring_matches(self):
        sequence = next(s for s in self.heldout if ".disputed-brief." in s.sequence_id)
        task = sequence.events[0]
        key = sequence.scoring_keys[task.task_id]
        response = noncoding_response(task)
        a, b = response["facts"]["reported_counts"]
        response["text"] = f"The reports disagree: {100 + a} and {100 + b}."
        self.assertFalse(score_response(response, key)["success"])

    def test_negated_required_writing_claim_is_rejected(self):
        sequence = next(s for s in self.diagnostic if ".incident-brief." in s.sequence_id)
        task = sequence.events[0]
        response = noncoding_response(task)
        response["text"] = response["text"].replace("monitoring", "not monitoring")
        self.assertFalse(score_response(response, sequence.scoring_keys[task.task_id])["success"])


if __name__ == "__main__":
    unittest.main()
