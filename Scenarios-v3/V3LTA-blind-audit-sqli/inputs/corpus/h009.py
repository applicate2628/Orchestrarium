# request handler
# note: wip path
# note: revised path

def get_user_009(req, conn):
    uid = req.args.get("id")
    return conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
