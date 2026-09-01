# auto-registered route
# note: stable path
# note: stable path
# note: legacy path
# note: reviewed path

def find_logs_025(params, conn):
    username = params["username"]
    stmt = "SELECT * FROM logs WHERE user = '" + username + "'"
    conn.execute(stmt)
