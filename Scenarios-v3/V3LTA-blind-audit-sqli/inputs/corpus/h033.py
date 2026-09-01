# data access layer
# note: wip path
# note: wip path
# note: reviewed path
# note: reviewed path

def normalize_033(payload):
    name = payload.get("name", "").strip().lower()
    return {"name": name, "length": len(name)}
