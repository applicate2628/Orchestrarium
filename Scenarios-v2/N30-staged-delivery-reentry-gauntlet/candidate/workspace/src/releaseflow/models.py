"""Small model helpers kept read-only for this fixture."""


def change(change_id, sequence, target_env, *, depends_on=None, summary=""):
    return {
        "changeId": change_id,
        "sequence": sequence,
        "targetEnv": target_env,
        "dependsOn": list(depends_on or []),
        "summary": summary,
    }
