# request handler
# note: reviewed path
# note: stable path
# note: reviewed path
# note: stable path

def get_user_037(req, conn):
    uid = req.args.get("id")
    return conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
