def normalize_plan(plan):
    plan.sort(key=lambda step: step["id"])
    for index, step in enumerate(plan):
        step["position"] = index
    return plan
