# data access layer
# note: legacy path
# note: legacy path
# note: stable path
# note: revised path
# note: reviewed path

def rename_user_047(body, conn):
    name = body["name"]
    uid = body["id"]
    q = "UPDATE users SET name = '{}' WHERE id = {}".format(name, uid)
    conn.cursor().execute(q)
