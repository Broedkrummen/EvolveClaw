"""Authored batch boundaries, independent grading and no-spend planning."""
import asyncio
from collections import Counter
from copy import deepcopy
import json
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evaluation.batches import CATEGORIES, batch_manifest, export_batches, role_sequences
from evaluation.run_models import CONDITIONS, evaluation_plan, selected_sequences, run_model_evaluation
from evaluation.scenarios import FakeWorld, Feedback, ScoringKey, Task, validate_manifest
from evaluation.scoring import score_response
from test_model_integration import FixtureTransport, configuration


class RoleTransport(FixtureTransport):
    """Use public fixture contracts, never the independent scorer, for mock proof."""
    async def __call__(self, url, payload, headers, timeout):
        messages = payload["messages"]
        if messages[0]["role"] != "system":
            return await super().__call__(url, payload, headers, timeout)
        public = json.loads(messages[1]["content"])
        if not public["tools"]:
            response = {"tool_calls": [], "answer": {"acknowledged": True}}
        elif len(messages) == 2 and public.get("executing_role") == "Planner":
            response = {"tool_calls": [], "delegations": [{"role": "Browser", "instruction": public["instruction"]}], "answer": None}
        elif len(messages) == 2:
            response = {"tool_calls": [t for t in public["tools"] if not t.get("input_schema")], "answer": None}
        else:
            from evaluation.coding_tasks import coding_response
            from evaluation.role_tasks import noncoding_response
            # The test fixture's public request and observed fixture result are
            # all this oracle can inspect. Its Task has no scorer reference.
            observations = json.loads(messages[-1]["content"].split(": ", 1)[1])
            if "delegated_role" in observations[0]:
                answer = observations[0]["result"]
            elif any(o["name"] == "code.check" for o in observations):
                self.asserted_public_check = True
                prior = json.loads(messages[-2]["content"])
                answer = {"code": prior["tool_calls"][0]["arguments"]["code"]}
            else:
                from evaluation.scenarios import Scope, ToolFixture
                task = Task(public["task_id"], public["instruction"], Scope(**public["scope"]),
                    tuple(ToolFixture(o["name"], next(t["arguments"] for t in public["tools"] if t["name"] == o["name"]), o["result"])
                          for o in observations), public["topic"])
                answer = coding_response(task) if public["topic"].startswith("coding:") else noncoding_response(task)
            response = {"tool_calls": [], "answer": answer}
            if public["topic"].startswith("coding:") and "delegated_role" not in observations[0] and not any(o["name"] == "code.check" for o in observations):
                response = {"tool_calls": [{"name": "code.check", "arguments": answer}], "answer": None}
        self.requests.append(deepcopy(payload))
        return {"choices": [{"message": {"content": json.dumps(response)}}], "usage": {"prompt_tokens": 80, "completion_tokens": 30}}


class BatchTests(unittest.TestCase):
    def test_nested_fact_types_cannot_substitute_numbers_for_booleans(self):
        key = ScoringKey({"facts": {"sent": False, "recipients": [True]}})
        self.assertTrue(score_response({"facts": {"sent": False, "recipients": [True]}}, key)["success"])
        self.assertFalse(score_response({"facts": {"sent": 0, "recipients": [True]}}, key)["success"])
        self.assertFalse(score_response({"facts": {"sent": False, "recipients": [1]}}, key)["success"])

    def test_complete_counts_disjointness_and_variant_spreading(self):
        rows = batch_manifest()
        self.assertEqual(Counter(r["split"] for r in rows), {"diagnostic": 5, "heldout": 50})
        sequences = [*role_sequences("diagnostic"), *role_sequences("heldout")]
        validate_manifest([s.manifest_entry() for s in sequences])
        self.assertEqual(Counter(s.split for s in sequences), {"diagnostic": 50, "heldout": 500})
        for split, families in (("diagnostic", 25), ("heldout", 100)):
            self.assertEqual(len({s.family_id for s in sequences if s.split == split}), families)
        for row in rows:
            self.assertEqual(row["sequence_count"], 10)
            self.assertEqual(row["five_condition_runs"], 50)
            self.assertEqual(row["future_probe_count"], 20)
            self.assertGreaterEqual(row["family_clusters"], 5)

    def test_every_batch_can_be_selected_and_planned_without_model_or_credentials(self):
        with patch("evaluation.models.BudgetedModel", side_effect=AssertionError("no model")), \
             patch("evaluation.models.os.environ.get", side_effect=AssertionError("no credentials")):
            for batch in batch_manifest():
                plan = evaluation_plan(configuration(), split=batch["split"], batch_id=batch["batch_id"])
                self.assertEqual(plan["sequence_ids"], batch["sequence_ids"])
                self.assertEqual(plan["sequence_runs"], 50)
                self.assertTrue(plan["complete_batch_selection"])
                self.assertEqual(plan["api_calls"], 0)
        with self.assertRaises(ValueError):
            selected_sequences("diagnostic", batch_id="heldout.coding.01")
        with self.assertRaises(ValueError):
            selected_sequences("diagnostic", sequence_ids=["anything"], batch_id="diagnostic.coding.01")

    def test_export_separates_grader_and_preserves_explicit_public_contracts(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "fixtures"
            manifest = export_batches(out)
            self.assertEqual(manifest["api_calls"], 0)
            public = json.loads((out / "public/sequences.json").read_text())
            grader = json.loads((out / "scorer-only/scoring_keys.json").read_text())
            self.assertEqual(manifest["public_fixture_sha256"], sha256((out / "public/sequences.json").read_bytes()).hexdigest())
            self.assertEqual(manifest["scoring_keys_sha256"], sha256((out / "scorer-only/scoring_keys.json").read_bytes()).hexdigest())
            self.assertEqual(set(public), set(grader))
            for sequence in role_sequences("diagnostic"):
                for event in sequence.events:
                    if isinstance(event, Task):
                        self.assertNotIn("grading", event.public_request())
                        self.assertNotIn("required_fields", event.public_request())
                        self.assertNotIn("scoring_keys", public[sequence.sequence_id])
            with self.assertRaises(FileExistsError):
                export_batches(out)

    def test_nonempty_text_and_content_constraints_are_independently_enforced(self):
        writing = next(s for s in role_sequences("diagnostic") if s.category == "writing")
        task = next(t for t in writing.events if isinstance(t, Task))
        from evaluation.role_tasks import noncoding_response
        answer = noncoding_response(task)
        key = writing.scoring_keys[task.task_id]
        self.assertTrue(score_response(answer, key)["success"])
        for text in ("", "irrelevant words", "padding " * (key.grading["max_words"] + 1)):
            bad = {**answer, key.grading["text_field"]: text}
            self.assertFalse(score_response(bad, key)["success"])

    def test_each_new_category_executes_all_five_actual_adapters_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            for category in CATEGORIES:
                batch = f"diagnostic.{category}.01"
                transport = RoleTransport()
                summary = asyncio.run(run_model_evaluation(configuration(max_calls=10000), Path(tmp) / category,
                    split="diagnostic", batch_id=batch, sequence_limit=1, conditions=CONDITIONS,
                    transport=transport, offline_mock=True))
                self.assertEqual(summary["status"], "completed")
                self.assertEqual(summary["sequence_runs"], 5)
                self.assertFalse(summary["efficacy_evidence"])
                if category == "coding":
                    self.assertTrue(transport.asserted_public_check)
                for result in summary["conditions"].values():
                    self.assertEqual(result["metrics"]["future_task_success"]["count"], 2)


if __name__ == "__main__":
    unittest.main()
