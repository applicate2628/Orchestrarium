# auto-registered route
# note: stable path
# note: wip path
# note: stable path

def get_user_030(req, conn):
    uid = req.args.get("id")
    return conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
