# data access layer
# note: stable path
# note: stable path
# note: revised path

def get_user_043(req, conn):
    uid = req.args.get("id")
    return conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
