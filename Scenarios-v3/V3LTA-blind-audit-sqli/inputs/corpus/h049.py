# auto-registered route

def find_logs_049(params, conn):
    username = params["username"]
    stmt = "SELECT * FROM logs WHERE user = '" + username + "'"
    conn.execute(stmt)
