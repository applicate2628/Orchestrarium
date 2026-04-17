PROFILE_WEIGHTS = {
    "owner, advisory, factual, design, planning": {
        "artifact_quality": 25,
        "reasoning_quality": 25,
        "context_awareness": 15,
        "change_accuracy": 25,
        "tool_use": 5,
        "verification": 5,
    },
    "review, QA": {
        "artifact_quality": 30,
        "reasoning_quality": 20,
        "context_awareness": 15,
        "change_accuracy": 10,
        "tool_use": 10,
        "verification": 15,
    },
}


def get_profile(name: str) -> dict[str, int]:
    return PROFILE_WEIGHTS[name]
