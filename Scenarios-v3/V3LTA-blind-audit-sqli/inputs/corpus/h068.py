# auto-registered route
# note: stable path
# note: reviewed path
# note: legacy path

def normalize_068(payload):
    name = payload.get("name", "").strip().lower()
    return {"name": name, "length": len(name)}
