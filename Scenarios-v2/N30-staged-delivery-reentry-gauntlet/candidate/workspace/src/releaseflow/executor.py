"""Resume-safe release execution."""


def execute_plan(plan, ledger, *, attempt=1, crash_after=None):
    """Apply plan items to the ledger and return the ledger.

    BUG: the action key includes attempt, so retry/resume replays already-applied work.
    """
    ledger.setdefault("applied", [])
    ledger.setdefault("audit", [])

    for index, item in enumerate(plan, start=1):
        action_key = f"{item['changeId']}:{item['targetEnv']}:attempt-{attempt}"
        record = {
            "actionKey": action_key,
            "changeId": item["changeId"],
            "targetEnv": item["targetEnv"],
            "sequence": item.get("sequence", 0),
            "status": "applied",
        }
        ledger["applied"].append(record)
        ledger["audit"].append({"event": "applied", "actionKey": action_key})
        if crash_after is not None and index >= crash_after:
            raise RuntimeError("simulated crash after partial apply")

    return ledger
