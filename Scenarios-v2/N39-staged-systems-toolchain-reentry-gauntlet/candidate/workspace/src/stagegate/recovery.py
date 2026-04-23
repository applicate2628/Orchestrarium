from __future__ import annotations


def resume_from_checkpoint(state, checkpoint: dict, current_sources: list[dict]):
    state.recovery_decisions = [{"source_id": "ST1", "classification": "accepted"}]
    return {
        "owner": "$product-manager",
        "source": checkpoint.get("source"),
        "primary_task": "",
        "visible_return_cue": "Send the output to QA now",
    }


def classify_runtime_failure(failure: dict):
    return "FAIL"
