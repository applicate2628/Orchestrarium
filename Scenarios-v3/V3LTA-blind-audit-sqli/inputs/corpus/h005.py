# service handler module

def normalize_005(payload):
    name = payload.get("name", "").strip().lower()
    return {"name": name, "length": len(name)}
