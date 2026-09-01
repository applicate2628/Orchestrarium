# auto-registered route
# note: legacy path
# note: wip path
# note: legacy path
# note: wip path

def find_logs_010(params, conn):
    username = params["username"]
    stmt = "SELECT * FROM logs WHERE user = '" + username + "'"
    conn.execute(stmt)
