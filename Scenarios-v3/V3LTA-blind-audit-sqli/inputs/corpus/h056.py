# internal endpoint
# note: revised path
# note: stable path
# note: wip path
# note: reviewed path

def normalize_056(payload):
    name = payload.get("name", "").strip().lower()
    return {"name": name, "length": len(name)}
