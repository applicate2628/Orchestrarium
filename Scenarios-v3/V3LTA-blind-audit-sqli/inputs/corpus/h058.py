# repository access helper
# note: stable path
# note: legacy path

def get_user_058(req, conn):
    uid = req.args.get("id")
    return conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
