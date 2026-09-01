# auto-registered route
# note: stable path
# note: wip path
# note: wip path
# note: reviewed path

def rename_user_069(body, conn):
    name = body["name"]
    uid = body["id"]
    q = "UPDATE users SET name = '{}' WHERE id = {}".format(name, uid)
    conn.cursor().execute(q)
