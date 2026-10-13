"""A bounded real-model loop over isolated fake tools, with no grader inputs."""
from copy import deepcopy
import inspect
import json

from .scenarios import FakeWorld, Task


BASE_PROMPT = """You are an assistant completing an everyday task in a simulation.
Use only the advertised fake tools and their exact supplied arguments. Call the
relevant tool before answering when tools are available. Observe its returned
result; never claim an operation completed without evidence.
Return one JSON object on every step: {"tool_calls":[{"name":"tool name","arguments":{}}],"answer":null} to use tools, or
{"tool_calls":[],"answer":{}} for your final structured answer. Do not combine
tool calls and a final answer in one step. For completion questions answer with
{"completed":true|false}; for fact/source questions use {"value":...,"source_id":...};
for a preference or plan choice use {"value":...}. Your answer must follow the
current task and observed evidence. A supplied lesson can be wrong or irrelevant;
respect current instructions, source reliability, and the current audience/project.
"""


class AgentExecutionError(RuntimeError):
    pass


ROLE_STEP_LIMITS = {"Planner": 20, "Web Search": 3, "Analyzer": 3, "Browser": 5}
ROLE_PURPOSES = {"Planner": "Plan the task, delegate work, and combine subordinate results into the final answer.",
                 "Web Search": "Find and assess sources using the advertised simulated tools.",
                 "Analyzer": "Analyze data, constraints, and results using the advertised simulated tools.",
                 "Browser": "Inspect external information and execute advertised simulated tool operations."}


def parse_json_response(content):
    text = content.strip()
    if text.startswith("```json") and text.endswith("```"):
        text = text[7:-3].strip()
    elif text.startswith("```") and text.endswith("```"):
        text = text[3:-3].strip()
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("The assistant response must be a JSON object")
    calls, answer = value.get("tool_calls", []), value.get("answer")
    delegations = value.get("delegations", [])
    if not isinstance(calls, list) or len(calls) > 8:
        raise ValueError("tool_calls must be a list containing at most eight calls")
    if answer is not None and not isinstance(answer, dict):
        raise ValueError("answer must be a structured object or null")
    if not isinstance(delegations, list) or len(delegations) > 1:
        raise ValueError("delegations must contain at most one subordinate invocation per step")
    if (calls or delegations) and answer is not None:
        raise ValueError("Call tools before sending the final answer")
    if calls and delegations:
        raise ValueError("Choose either tool calls or a subordinate delegation per step")
    if not calls and not delegations and answer is None:
        raise ValueError("Return either tool calls or a final answer")
    for call in calls:
        if not isinstance(call, dict) or not isinstance(call.get("name"), str) or not isinstance(call.get("arguments"), dict):
            raise ValueError("Each tool call needs a name and argument object")
    for delegation in delegations:
        if not isinstance(delegation, dict) or delegation.get("role") not in ("Web Search", "Analyzer", "Browser") or not isinstance(delegation.get("instruction"), str) or not delegation["instruction"].strip():
            raise ValueError("A delegation requires an allowed subordinate role and an instruction")
    return value


class FakeWorldModelAgent:
    """One public request per task; each perspective gets a new fake world."""
    def __init__(self, model, max_steps=5, role="Planner", hierarchical=False):
        if not isinstance(max_steps, int) or isinstance(max_steps, bool) or max_steps <= 0:
            raise ValueError("max_steps must be a positive integer")
        self.model, self.max_steps, self.role = model, max_steps, role
        self.hierarchical = hierarchical
        self.last_runs = []

    def bind(self, task: Task):
        async def execute(public_task, perspective, guidance):
            # Use the existing public shape only. Reject a caller that slips a
            # scoring key or expected answer into the task envelope.
            if public_task != task.public_request():
                raise ValueError("Executor requires the exact learner-visible public task")
            return await self.run_task(task, perspective, guidance)
        return execute

    async def run_task(self, task: Task, perspective="single", guidance=None):
        world = FakeWorld(task)
        steps = []
        run = {"task_id": task.task_id, "perspective": perspective, "response": None,
               "steps": steps, "tool_calls": world.calls, "status": "running",
               "hierarchical": self.hierarchical, "role_invocations": []}
        self.last_runs.append(run)
        maximum = ROLE_STEP_LIMITS["Planner"] if self.hierarchical else self.max_steps
        try:
            response = await self._execute_role(task, world, self.role, task.instruction, maximum,
                                                perspective, guidance, run)
        except Exception as exc:
            run["status"] = "step-limit-exceeded" if isinstance(exc, AgentExecutionError) else "failed"
            run["error_type"] = type(exc).__name__
            raise
        run.update({"response": response, "status": "completed"})
        return deepcopy(response)

    async def _execute_role(self, task, world, role, instruction, maximum, perspective, guidance, run):
        invocation = {"role": role, "index": len(run["role_invocations"]) + 1,
                      "max_steps": maximum, "steps": 0, "status": "running"}
        run["role_invocations"].append(invocation)
        base_prompt = BASE_PROMPT
        public = task.public_request()
        if self.hierarchical:
            base_prompt += f"\nYour role is {role}. {ROLE_PURPOSES[role]}\n"
            if role == "Planner":
                base_prompt += ('Use subordinate roles for tool work; do not call fake tools directly. Delegate with '
                                '{"tool_calls":[],"delegations":[{"role":"Web Search|Analyzer|Browser","instruction":"specific work"}],"answer":null}. '
                                'Delegate one subtask per step, observe its result, then continue planning or answer.\n')
            else:
                base_prompt += "Execute this delegated subtask. You may call fake tools or answer, but cannot delegate further.\n"
            public = {**public, "delegated_instruction": instruction, "executing_role": role}
        history = [{"role": "user", "content": json.dumps(public)}]
        for index in range(maximum):
            prompt = guidance.prompt(role, base_prompt) if guidance else base_prompt
            reply = await self.model.generate([{"role": "system", "content": prompt}, *history])
            history.append({"role": "assistant", "content": reply.content})
            observations, error, parsed = [], None, None
            try:
                parsed = parse_json_response(reply.content)
                delegations = parsed.get("delegations", [])
                if delegations and (not self.hierarchical or role != "Planner"):
                    raise ValueError("Only the hierarchical Planner can delegate")
                if self.hierarchical and role == "Planner" and parsed.get("tool_calls"):
                    raise ValueError("The hierarchical Planner must delegate tool work to a subordinate")
                if parsed.get("answer") is not None and task.tools and not world.calls:
                    raise ValueError("No tool observation supports this final answer yet")
                for call in parsed.get("tool_calls", []):
                    try:
                        result = world.call(call["name"], call["arguments"])
                    except ValueError as exc:
                        result = {"status": "failed", "error": str(exc)}
                    observations.append({"name": call["name"], "result": result})
                    if result.get("status") == "failed":
                        error = RuntimeError(f"Simulated tool {call['name']} failed: {result.get('error', 'unknown error')}")
                for delegation in delegations:
                    try:
                        subordinate = await self._execute_role(task, world, delegation["role"], delegation["instruction"],
                            ROLE_STEP_LIMITS[delegation["role"]], perspective, guidance, run)
                        observations.append({"delegated_role": delegation["role"], "result": subordinate})
                    except AgentExecutionError as exc:
                        error = exc
                        observations.append({"delegated_role": delegation["role"], "error": str(exc)})
            except (ValueError, json.JSONDecodeError) as exc:
                error = exc
                observations.append({"format_error": str(exc)})
            learning = None
            if guidance:
                actions = {"tool_calls": parsed.get("tool_calls", []), "delegations": parsed.get("delegations", [])} if parsed else None
                learning = guidance.observe_step(role=role, base_prompt=base_prompt,
                    model_output=reply.content, tool_calls=json.dumps(actions) if actions else None,
                    observations=json.dumps(observations), error=error)
                if inspect.isawaitable(learning):
                    learning = await learning
            invocation["steps"] += 1
            run["steps"].append({"index": index + 1, "role": role, "invocation": invocation["index"], "model_output": reply.content,
                          "observations": deepcopy(observations), "error_type": type(error).__name__ if error else None,
                          "learning": learning})
            if parsed and parsed.get("answer") is not None and error is None:
                invocation["status"] = "completed"
                return deepcopy(parsed["answer"])
            history.append({"role": "user", "content": "Observed simulated tool/format results: " + json.dumps(observations)})
        invocation["status"] = "step-limit-exceeded"
        raise AgentExecutionError(f"The bounded {role} invocation reached its {maximum}-step limit without a final answer")
