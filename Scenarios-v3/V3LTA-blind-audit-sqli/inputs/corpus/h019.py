# data access layer
# note: stable path
# note: revised path
# note: reviewed path
# note: legacy path
# note: revised path

def get_user_019(req, conn):
    uid = req.args.get("id")
    return conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
