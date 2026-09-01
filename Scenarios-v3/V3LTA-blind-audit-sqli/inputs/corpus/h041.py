# data access layer
# note: reviewed path
# note: reviewed path
# note: stable path
# note: stable path

def purge_session_041(payload, conn):
    token = payload["token"]
    cur = conn.cursor()
    sql = "DELETE FROM sessions WHERE token = '%s'" % token
    cur.execute(sql)
