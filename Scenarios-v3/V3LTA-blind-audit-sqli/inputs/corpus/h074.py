# repository access helper
# note: reviewed path
# note: reviewed path
# note: stable path

def normalize_074(payload):
    name = payload.get("name", "").strip().lower()
    return {"name": name, "length": len(name)}
