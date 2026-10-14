"""Executable coding-fixture gates, including bounded hostile submissions."""
from collections import Counter
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from evaluation.coding_tasks import (
    DIAGNOSTIC_FAMILIES, HELDOUT_FAMILIES, coding_metadata, coding_response,
    coding_sequences, grade_code, public_code_check,
)
from evaluation.scenarios import FakeWorld, Feedback, Task, pilot_sequences
from evaluation.scoring import score_response


class CodingFixtureTests(unittest.TestCase):
    def test_counts_clusters_phases_and_split_disjointness(self):
        diagnostic, heldout = coding_sequences(), coding_sequences("heldout")
        self.assertEqual((len(diagnostic),len(heldout)),(10,100))
        self.assertEqual(len(DIAGNOSTIC_FAMILIES),5)
        self.assertEqual(len(HELDOUT_FAMILIES),20)
        self.assertFalse(set(DIAGNOSTIC_FAMILIES).intersection(HELDOUT_FAMILIES))
        self.assertEqual(set(Counter(s.family_id for s in diagnostic).values()),{2})
        self.assertEqual(set(Counter(s.family_id for s in heldout).values()),{5})
        all_sequences=(*diagnostic,*heldout)
        self.assertEqual(len({s.sequence_id for s in all_sequences}),110)
        ids=set()
        for sequence in all_sequences:
            self.assertEqual(sequence.category,"coding")
            self.assertEqual(sequence.cluster_id,sequence.family_id)
            self.assertIsInstance(sequence.events[2],Feedback)
            self.assertIsNone(sequence.events[2].value)
            tasks=[e for e in sequence.events if isinstance(e,Task)]
            self.assertEqual([t.phase for t in tasks],["learning","learning","future","future"])
            self.assertEqual(len({json.dumps(t.tools[0].result,sort_keys=True) for t in tasks}),4)
            self.assertEqual(set(sequence.scoring_keys),{t.task_id for t in tasks})
            for task in tasks:
                self.assertNotIn(task.task_id,ids); ids.add(task.task_id)
                self.assertEqual(sequence.scoring_keys[task.task_id].required_fields,{})
                self.assertEqual(sequence.scoring_keys[task.task_id].grading["kind"],"coding")
        self.assertEqual(len(ids),440)
        self.assertFalse({s.family_id for s in all_sequences}.intersection(s.family_id for s in pilot_sequences()))
        self.assertFalse(coding_metadata()["published_benchmark"])
        with self.assertRaises(ValueError):coding_sequences("development")

    def test_correct_public_contract_implementations_pass_all_440_private_regressions(self):
        checked_dispatch=set()
        for sequence in (*coding_sequences(),*coding_sequences("heldout")):
            for task in sequence.events:
                if not isinstance(task,Task):continue
                response=coding_response(task)
                # The helper is unaffected if a private key is destroyed: its
                # input and output use only the advertised inspect contract.
                key=sequence.scoring_keys[task.task_id]
                self.assertEqual(grade_code(response,key.grading),[],task.task_id)
                if sequence.family_id not in checked_dispatch:
                    self.assertTrue(score_response(response,key)["success"],task.task_id)
                    checked_dispatch.add(sequence.family_id)

    def test_every_original_program_fails_real_regression_execution(self):
        for sequence in (*coding_sequences(),*coding_sequences("heldout")):
            for task in sequence.events:
                if not isinstance(task,Task):continue
                original=task.tools[0].result["source_code"]
                errors=grade_code({"code":original},sequence.scoring_keys[task.task_id].grading)
                self.assertTrue(errors,task.task_id)
                self.assertTrue(all(error.startswith("coding_test_") for error in errors),(task.task_id,errors))

    def test_public_dynamic_checker_executes_only_public_cases_and_preserves_results(self):
        # All mechanisms have an actual source repair, reachable through the
        # advertised dynamic tool rather than a manufactured passed flag.
        for split in ("diagnostic","heldout"):
            seen=set()
            for sequence in coding_sequences(split):
                if sequence.family_id in seen:continue
                seen.add(sequence.family_id)
                task=sequence.events[0]
                world=FakeWorld(task)
                spec=world.call("code.inspect",task.tools[0].arguments)
                source=coding_response(task)["code"]
                result=world.call("code.check",{"code":source})
                self.assertEqual(result["status"],"completed",task.task_id)
                self.assertEqual((result["passed"],result["total"]),(2,2))
                self.assertEqual(len(result["tests"]),2)
                self.assertEqual([r["actual"] for r in result["tests"]],[c["expected"] for c in spec["tests"]])
                self.assertEqual(task.tools[1].input_schema,{"code":"string"})
                self.assertEqual(task.tools[1].handler,"coding-check")
                self.assertEqual(task.tools[1].arguments,{})
                self.assertEqual(task.tools[0].result,task.tools[1].result)
                with self.assertRaises(ValueError):world.call("code.check",{})
                with self.assertRaises(ValueError):world.call("code.check",{"code":source,"extra":True})
                with self.assertRaises(ValueError):world.call("code.inspect",{})
                public=task.public_request()
                def public_keys(value):
                    if isinstance(value,dict):
                        return set(value).union(*(public_keys(child) for child in value.values()))
                    if isinstance(value,list):
                        return set().union(*(public_keys(child) for child in value))
                    return set()
                self.assertFalse({"grading","expected","tests","source_code"}.intersection(public_keys(public)))
                self.assertNotEqual(spec["source_code"],source)
                private=sequence.scoring_keys[task.task_id].grading["tests"]
                self.assertGreater(len(private),len(spec["tests"]))
                detached=deepcopy(spec); detached["tests"]=[]
                self.assertEqual(len(task.tools[0].result["tests"]),2)

    def test_integer_boolean_types_and_input_mutation_are_checked(self):
        grading={"kind":"coding","function_name":"solve","tests":[{"args":[[1,2]],"expected":1}]}
        self.assertTrue(grade_code({"code":"def solve(values):\n    return True\n"},grading))
        self.assertTrue(grade_code({"code":"def solve(values):\n    values.pop()\n    return 1\n"},grading))
        self.assertEqual(grade_code({"code":"def solve(values):\n    return len(values) - 1\n"},grading),[])
        list_grading={"kind":"coding","function_name":"solve","tests":[{"args":[[1,2]],"expected":[1,2]}]}
        self.assertTrue(grade_code({"code":"def solve(values):\n    return tuple(values)\n"},list_grading))

    def test_malicious_import_reflection_io_and_infinite_code_are_bounded(self):
        grading={"kind":"coding","function_name":"solve","tests":[{"args":[0],"expected":0}]}
        with tempfile.TemporaryDirectory() as directory:
            marker=Path(directory)/"must-not-exist"
            candidates=[
                "import os\ndef solve(x):\n    return os.environ.get('EC_SYNTHETIC_SECRET')\n",
                "def solve(x):\n    return x.__class__.__base__.__subclasses__()\n",
                "def solve(x):\n    return __builtins__\n",
                "def solve(x):\n    global missing\n    return missing\n",
                "def solve(x):\n    open("+repr(str(marker))+", 'w').write('bad')\n    return 0\n",
                "def solve(x):\n    return eval('0')\n",
            ]
            with patch.dict(os.environ,{"EC_SYNTHETIC_SECRET":"test-only-secret"}):
                for source in candidates:
                    self.assertTrue(grade_code({"code":source},grading))
                self.assertFalse(marker.exists())
            started=time.monotonic()
            errors=grade_code({"code":"def solve(x):\n    while True:\n        pass\n"},grading)
            self.assertEqual(errors,["coding_execution_limit"])
            self.assertLess(time.monotonic()-started,3)
        self.assertEqual(grade_code({},grading),["code"])


if __name__ == "__main__":unittest.main()
