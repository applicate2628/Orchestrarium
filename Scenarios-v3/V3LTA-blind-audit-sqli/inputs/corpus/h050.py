# repository access helper
# note: revised path
# note: revised path

def get_user_050(req, conn):
    uid = req.args.get("id")
    return conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
