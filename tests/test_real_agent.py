"""Offline checks of the authored hierarchical action and reflection contracts."""
import asyncio
from copy import deepcopy
from dataclasses import replace
import json
from types import SimpleNamespace
import unittest

from evaluation.real_agent import (
    AgentExecutionError, BASE_PROMPT, FakeWorldModelAgent, HIERARCHICAL_PRIOR_CONTEXT_LIMIT,
    parse_json_response,
)
from evaluation.scenarios import pilot_sequences


def booking_task():
    return next(sequence.events[0] for sequence in pilot_sequences()
                if sequence.sequence_id == "pilot.booking-failure.01")


class CaptureGuidance:
    def __init__(self):
        self.steps = []

    def prompt(self, role, base_prompt):
        return base_prompt

    async def observe_step(self, **step):
        self.steps.append(deepcopy(step))
        return {"accepted": False}


class PromptFollowingModel:
    """Use the advertised Planner example and actual returned fake evidence."""
    def __init__(self, delegations=1):
        self.requests = []
        self.remaining_delegations = delegations

    async def generate(self, messages):
        self.requests.append(deepcopy(messages))
        public = json.loads(messages[1]["content"])
        if public["executing_role"] == "Planner":
            if self.remaining_delegations:
                self.remaining_delegations -= 1
                advertised = messages[0]["content"].split("Delegate with ", 1)[1]
                response, _ = json.JSONDecoder().raw_decode(advertised)
                # A model copying this exact JSON example must pass admission.
                parse_json_response(json.dumps(response))
            else:
                observed = json.loads(messages[-1]["content"].split(": ", 1)[1])
                response = {"tool_calls": [], "answer": observed[0]["result"]}
        elif len(messages) == 2:
            tool = public["tools"][0]
            response = {"tool_calls": [deepcopy(tool)], "answer": None}
        else:
            observed = json.loads(messages[-1]["content"].split(": ", 1)[1])
            result = observed[0]["result"]
            response = {"tool_calls": [], "answer": {
                "completed": result["status"] == "completed", "error": result.get("error")}}
        return SimpleNamespace(content=json.dumps(response))


class HierarchicalAgentTests(unittest.TestCase):
    def test_advertised_planner_example_executes_child_tool_and_final_answer(self):
        task, model, guidance = booking_task(), PromptFollowingModel(), CaptureGuidance()
        agent = FakeWorldModelAgent(model, hierarchical=True)
        response = asyncio.run(agent.run_task(task, guidance=guidance))
        self.assertEqual(response, {"completed": False, "error": "Service unavailable"})
        run = agent.last_runs[0]
        self.assertEqual(run["tool_calls"], [{"name": "booking.reserve", "arguments": {"item": "initial-1"},
                                              "result": task.tools[0].result}])
        planner_prompt = model.requests[0][0]["content"]
        self.assertNotIn('"role":"Web Search|Analyzer|Browser"', planner_prompt)
        self.assertNotIn('"tool_calls":[{"name":', planner_prompt)
        self.assertIn("The legal subordinate roles are Web Search, Analyzer, and Browser", planner_prompt)
        self.assertEqual([(r["role"], r["max_steps"], r["steps"]) for r in run["role_invocations"]],
                         [("Planner", 20, 2), ("Browser", 5, 2)])

    def test_terminal_reflection_contains_prior_observed_tool_evidence(self):
        guidance = CaptureGuidance()
        agent = FakeWorldModelAgent(PromptFollowingModel(), hierarchical=True)
        asyncio.run(agent.run_task(booking_task(), guidance=guidance))
        browser = [step for step in guidance.steps if step["role"] == "Browser"]
        first, final = (json.loads(step["observations"]) for step in browser)
        self.assertEqual(first["prior_invocation_public_context"], "")
        self.assertEqual(final["current_step"], {
            "actions": {"tool_calls": [], "delegations": []}, "observations": []})
        prior = json.loads(final["prior_invocation_public_context"])
        self.assertEqual(prior["actions"]["tool_calls"][0]["name"], "booking.reserve")
        self.assertEqual(prior["observations"][0]["result"],
                         {"status": "failed", "error": "Service unavailable"})
        self.assertFalse(final["prior_context_truncated"])
        planner_final = json.loads(guidance.steps[-1]["observations"])
        self.assertIn('"delegated_role": "Browser"', planner_final["prior_invocation_public_context"])
        self.assertNotIn('"name": "booking.reserve"', planner_final["prior_invocation_public_context"])

    def test_prior_context_is_bounded_without_truncating_the_actual_tool_trace(self):
        original = booking_task()
        result = {"status": "failed", "error": "public synthetic diagnostic " + "x" * 10000}
        task = replace(original, tools=(replace(original.tools[0], result=result),))
        guidance = CaptureGuidance()
        agent = FakeWorldModelAgent(PromptFollowingModel(), hierarchical=True)
        asyncio.run(agent.run_task(task, guidance=guidance))
        browser = [json.loads(step["observations"]) for step in guidance.steps if step["role"] == "Browser"]
        self.assertTrue(browser[-1]["prior_context_truncated"])
        self.assertLessEqual(len(browser[-1]["prior_invocation_public_context"]), HIERARCHICAL_PRIOR_CONTEXT_LIMIT)
        self.assertEqual(browser[0]["current_step"]["observations"][0]["result"], result)
        self.assertEqual(agent.last_runs[0]["tool_calls"][0]["result"], result)

    def test_prior_context_resets_for_each_subordinate_invocation(self):
        guidance = CaptureGuidance()
        agent = FakeWorldModelAgent(PromptFollowingModel(delegations=2), hierarchical=True)
        asyncio.run(agent.run_task(booking_task(), guidance=guidance))
        browser = [json.loads(step["observations"]) for step in guidance.steps if step["role"] == "Browser"]
        self.assertEqual(len(browser), 4)
        self.assertEqual(browser[0]["prior_invocation_public_context"], "")
        self.assertEqual(browser[2]["prior_invocation_public_context"], "")
        self.assertEqual(len(agent.last_runs[0]["tool_calls"]), 2)

    def test_flat_agent_uses_shared_protocol_with_original_observation_shape(self):
        task, guidance = booking_task(), CaptureGuidance()

        class FlatModel:
            def __init__(self):
                self.requests = []

            async def generate(self, messages):
                self.requests.append(deepcopy(messages))
                response = ({"tool_calls": [{"name": task.tools[0].name,
                                              "arguments": task.tools[0].arguments}], "answer": None}
                            if len(self.requests) == 1 else {"tool_calls": [], "answer": {"completed": False}})
                return SimpleNamespace(content=json.dumps(response))

        model = FlatModel()
        agent = FakeWorldModelAgent(model)
        asyncio.run(agent.run_task(task, guidance=guidance))
        self.assertEqual(model.requests[0], [{"role": "system", "content": BASE_PROMPT},
                                            {"role": "user", "content": json.dumps(task.public_request())}])
        self.assertEqual(json.loads(guidance.steps[0]["observations"]),
                         [{"name": task.tools[0].name, "result": task.tools[0].result}])
        self.assertEqual(guidance.steps[1]["observations"], "[]")
        self.assertEqual([r["max_steps"] for r in agent.last_runs[0]["role_invocations"]], [5])

    def test_copying_complete_final_examples_returns_nested_answers_after_actual_evidence(self):
        class FinalExampleModel:
            async def generate(self, messages):
                prompt, public = messages[0]["content"], json.loads(messages[1]["content"])
                role = public.get("executing_role")
                if len(messages) == 2:
                    if role == "Planner":
                        response, _ = json.JSONDecoder().raw_decode(prompt.split("Delegate with ", 1)[1])
                    else:
                        response = {"tool_calls": [deepcopy(public["tools"][0])], "answer": None}
                else:
                    observations = json.loads(messages[-1]["content"].split(": ", 1)[1])
                    result = observations[0]["result"]
                    completed = result["completed"] if role == "Planner" else result["status"] == "completed"
                    label = "Illustrative completion success: " if completed else "Illustrative completion failure: "
                    response, _ = json.JSONDecoder().raw_decode(prompt.split(label, 1)[1])
                return SimpleNamespace(content=json.dumps(response))

        sequence = next(s for s in pilot_sequences() if s.sequence_id == "pilot.booking-failure.01")
        for hierarchical in (False, True):
            for task, completed in ((sequence.events[0], False), (sequence.events[-1], True)):
                with self.subTest(hierarchical=hierarchical, completed=completed):
                    guidance = CaptureGuidance()
                    agent = FakeWorldModelAgent(FinalExampleModel(), hierarchical=hierarchical)
                    response = asyncio.run(agent.run_task(task, guidance=guidance))
                    self.assertEqual(response, {"completed": completed})
                    self.assertEqual(agent.last_runs[0]["status"], "completed")
                    self.assertEqual(len(agent.last_runs[0]["tool_calls"]), 1)
                    self.assertTrue(all(step["error"] is None for step in guidance.steps
                                        if json.loads(step["model_output"]).get("answer") is not None))
                    self.assertEqual(json.loads(guidance.steps[-1]["model_output"]),
                                     {"tool_calls": [], "answer": {"completed": completed}})

    def test_step_limit_error_has_typed_role_and_limit_without_changing_cap(self):
        class BareAnswerModel:
            async def generate(self, messages):
                return SimpleNamespace(content='{"completed":false}')

        agent = FakeWorldModelAgent(BareAnswerModel(), max_steps=2)
        with self.assertRaises(AgentExecutionError) as caught:
            asyncio.run(agent.run_task(booking_task()))
        self.assertEqual(caught.exception.kind, "step-limit-exceeded")
        self.assertEqual(caught.exception.role, "Planner")
        self.assertEqual(caught.exception.limit, 2)
        self.assertEqual(agent.last_runs[0]["role_invocations"][0]["steps"], 2)
        self.assertEqual(agent.last_runs[0]["status"], "step-limit-exceeded")


if __name__ == "__main__":
    unittest.main()
