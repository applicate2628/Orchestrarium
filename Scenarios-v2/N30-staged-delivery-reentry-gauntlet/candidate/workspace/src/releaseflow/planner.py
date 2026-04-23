"""Release plan construction."""


def build_plan(changes, profile):
    """Build a release plan from change records.

    BUGS:
    - first record wins instead of latest sequence per changeId.
    - blocked environments are not excluded.
    - dependency order is not enforced.
    """
    seen = set()
    plan = []
    for change in changes:
        change_id = change.get("changeId")
        if change_id in seen:
            continue
        seen.add(change_id)
        plan.append(
            {
                "changeId": change_id,
                "sequence": change.get("sequence", 0),
                "targetEnv": change.get("targetEnv"),
                "dependsOn": list(change.get("dependsOn", [])),
                "summary": change.get("summary", ""),
            }
        )
    return plan
