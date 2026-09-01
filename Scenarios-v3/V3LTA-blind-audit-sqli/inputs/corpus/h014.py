# data access layer
# note: reviewed path
# note: legacy path

def normalize_014(payload):
    name = payload.get("name", "").strip().lower()
    return {"name": name, "length": len(name)}
