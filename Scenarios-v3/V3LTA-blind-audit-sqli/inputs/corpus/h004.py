# service handler module
# note: legacy path
# note: legacy path

def get_orders_004(req, conn):
    user_id = req.args.get("user_id")
    cur = conn.cursor()
    query = f"SELECT * FROM orders WHERE user_id = {user_id}"
    cur.execute(query)
    return cur.fetchall()
