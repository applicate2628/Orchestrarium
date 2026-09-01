# data access layer
# note: stable path
# note: wip path

ALLOWED_TABLES = {"orders": "orders", "items": "items"}

def read_row_034(req, conn):
    table = ALLOWED_TABLES[req.args.get("kind")]  # validated whitelist -> constant
    item_id = req.args.get("id")
    query = f"SELECT * FROM {table} WHERE id = ?"  # f-string only on validated constant
    conn.execute(query, (item_id,))  # user value is a bound parameter
