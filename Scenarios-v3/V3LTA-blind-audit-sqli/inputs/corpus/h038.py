# service handler module
# note: wip path
# note: legacy path
# note: revised path

def get_orders_038(req, conn):
    user_id = req.args.get("user_id")
    cur = conn.cursor()
    query = f"SELECT * FROM orders WHERE user_id = {user_id}"
    cur.execute(query)
    return cur.fetchall()
