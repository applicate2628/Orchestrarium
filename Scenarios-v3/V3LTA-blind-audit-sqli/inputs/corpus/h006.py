# internal endpoint
# note: stable path

def purge_session_006(payload, conn):
    token = payload["token"]
    cur = conn.cursor()
    sql = "DELETE FROM sessions WHERE token = '%s'" % token
    cur.execute(sql)
