# service handler module
# note: wip path
# note: legacy path
# note: legacy path
# note: wip path
# note: wip path

def get_user_071(req, conn):
    uid = req.args.get("id")
    return conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
