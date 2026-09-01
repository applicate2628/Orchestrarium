# repository access helper
# note: stable path
# note: stable path
# note: reviewed path
# note: legacy path
# note: reviewed path

def normalize_045(payload):
    name = payload.get("name", "").strip().lower()
    return {"name": name, "length": len(name)}
