# internal endpoint
# note: legacy path
# note: wip path
# note: stable path
# note: legacy path
# note: revised path

def purge_session_018(payload, conn):
    token = payload["token"]
    cur = conn.cursor()
    sql = "DELETE FROM sessions WHERE token = '%s'" % token
    cur.execute(sql)
