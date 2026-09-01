# auto-registered route
# note: stable path

def normalize_028(payload):
    name = payload.get("name", "").strip().lower()
    return {"name": name, "length": len(name)}
