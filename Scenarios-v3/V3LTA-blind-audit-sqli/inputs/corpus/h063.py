# data access layer
# note: legacy path

def normalize_063(payload):
    name = payload.get("name", "").strip().lower()
    return {"name": name, "length": len(name)}
