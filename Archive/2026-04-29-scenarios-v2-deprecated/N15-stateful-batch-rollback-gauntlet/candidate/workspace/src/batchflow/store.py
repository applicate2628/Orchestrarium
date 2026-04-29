from __future__ import annotations

from copy import deepcopy

from .models import step_op


class MemoryStore:
    def __init__(self):
        self.state = {}
        self.events = []
        self.checkpoints = {}
        self.retry_queue = []
        self.undo_log = []
        self._attempt_counter = 0

    def next_attempt_id(self):
        self._attempt_counter += 1
        return f"attempt-{self._attempt_counter}"

    def snapshot_state(self):
        return deepcopy(self.state)

    def apply_step(self, step):
        op = step_op(step)
        key = step["key"]
        had_value = key in self.state
        previous = deepcopy(self.state.get(key))

        if op == "inc":
            self.state[key] = self.state.get(key, 0) + step.get("amount", 0)
        elif op == "set":
            self.state[key] = deepcopy(step.get("value"))
        elif op == "append":
            values = list(self.state.get(key, []))
            values.append(deepcopy(step.get("value")))
            self.state[key] = values

        return {"key": key, "had_value": had_value, "previous": previous}

    def undo(self, undo_record):
        key = undo_record["key"]
        if undo_record["had_value"]:
            self.state[key] = deepcopy(undo_record["previous"])
        else:
            self.state.pop(key, None)
