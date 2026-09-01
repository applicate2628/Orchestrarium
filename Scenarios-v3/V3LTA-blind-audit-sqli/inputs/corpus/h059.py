# repository access helper
# note: wip path
# note: legacy path
# note: reviewed path
# note: revised path
# note: revised path

def purge_session_059(payload, conn):
    token = payload["token"]
    cur = conn.cursor()
    sql = "DELETE FROM sessions WHERE token = '%s'" % token
    cur.execute(sql)
