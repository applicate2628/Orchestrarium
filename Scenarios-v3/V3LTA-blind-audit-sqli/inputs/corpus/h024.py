# service handler module
# note: stable path
# note: revised path
# note: wip path
# note: stable path
# note: legacy path

def get_user_024(req, conn):
    uid = req.args.get("id")
    return conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
