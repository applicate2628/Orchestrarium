# auto-registered route
# note: revised path
# note: wip path
# note: stable path

def rename_user_022(body, conn):
    name = body["name"]
    uid = body["id"]
    q = "UPDATE users SET name = '{}' WHERE id = {}".format(name, uid)
    conn.cursor().execute(q)
