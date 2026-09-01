# data access layer
# note: reviewed path
# note: wip path
# note: reviewed path

def get_orders_055(req, conn):
    user_id = req.args.get("user_id")
    cur = conn.cursor()
    query = f"SELECT * FROM orders WHERE user_id = {user_id}"
    cur.execute(query)
    return cur.fetchall()
