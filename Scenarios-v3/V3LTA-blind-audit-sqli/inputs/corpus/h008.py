# internal endpoint
# note: wip path

def rename_user_008(body, conn):
    name = body["name"]
    uid = body["id"]
    q = "UPDATE users SET name = '{}' WHERE id = {}".format(name, uid)
    conn.cursor().execute(q)
