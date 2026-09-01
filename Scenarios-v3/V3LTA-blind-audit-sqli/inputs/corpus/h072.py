# data access layer

def find_logs_072(params, conn):
    username = params["username"]
    stmt = "SELECT * FROM logs WHERE user = '" + username + "'"
    conn.execute(stmt)
