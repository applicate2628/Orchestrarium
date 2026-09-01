# data access layer
# note: legacy path
# note: wip path
# note: legacy path
# note: legacy path
# note: revised path

def normalize_021(payload):
    name = payload.get("name", "").strip().lower()
    return {"name": name, "length": len(name)}
