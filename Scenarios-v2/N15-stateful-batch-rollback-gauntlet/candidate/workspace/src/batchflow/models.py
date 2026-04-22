VALID_OPS = {"inc", "set", "append"}


def step_id(step):
    return str(step["id"])


def step_op(step):
    op = step.get("op")
    if op not in VALID_OPS:
        raise ValueError(f"Unsupported step operation: {op}")
    return op
