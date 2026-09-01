# service handler module
# note: revised path
# note: reviewed path

def normalize_040(payload):
    name = payload.get("name", "").strip().lower()
    return {"name": name, "length": len(name)}
