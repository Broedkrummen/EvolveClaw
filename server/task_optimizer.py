"""Narrow compatibility adapter for the pinned scope-optimizer 0.1.3 SDK.

That SDK keys two supposedly per-task counters by agent alone and supplies no
reset API. Keep those counters per (agent, task), serialize its shared memory
store, and expose a real reset without altering strategic memory's disk format.
"""
import asyncio
from scope import SCOPEOptimizer


class TaskScopedOptimizer(SCOPEOptimizer):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.lock = asyncio.Lock()
        self.task_counters: dict[tuple[str, str | None], tuple[int, int]] = {}
        self._promotion_succeeded = False
        add_rule = self.strategic_store.add_strategic_rule
        async def track_promotion(**kwargs):
            result = await add_rule(**kwargs)
            self._promotion_succeeded = bool(result)
            return result
        self.strategic_store.add_strategic_rule = track_promotion

    async def on_step_complete(self, *, agent_name, task_id=None, **kwargs):
        async with self.lock:
            key = (agent_name, task_id)
            applied, successful = self.task_counters.get(key, (0, 0))
            self._applied_rules_count[agent_name] = applied
            self._successful_steps_count[agent_name] = successful
            self._promotion_succeeded = False
            before = self.strategic_guidelines(agent_name)
            try:
                result = await super().on_step_complete(agent_name=agent_name, task_id=task_id, **kwargs)
                if result and result[1] == "strategic":
                    text, _ = result
                    persisted = self.strategic_guidelines(agent_name)
                    if self._promotion_succeeded:
                        # Consolidation may intentionally replace the raw suggestion.
                        # Only the authoritative memory should be reinjected afterward.
                        if persisted == before and text not in persisted:
                            return None
                    elif text not in persisted:
                        result = (text, "tactical")
                return result
            finally:
                self.task_counters[key] = (
                    self._applied_rules_count.get(agent_name, 0),
                    self._successful_steps_count.get(agent_name, 0),
                )

    async def reset_tactical(self, *, agent_name, task_id=None):
        async with self.lock:
            for key in list(self.task_counters):
                if key[0] == agent_name and (task_id is None or key[1] == task_id):
                    del self.task_counters[key]
            for key, agents in list(self._applied_rules_by_task.items()):
                if task_id is None or key == task_id:
                    agents.pop(agent_name, None)
                    if not agents:
                        del self._applied_rules_by_task[key]
            self._applied_rules_count.pop(agent_name, None)
            self._successful_steps_count.pop(agent_name, None)

    def strategic_guidelines(self, agent_name):
        return [rule["rule"] for rules in self.strategic_store.get_strategic_rules(agent_name).values() for rule in rules]
