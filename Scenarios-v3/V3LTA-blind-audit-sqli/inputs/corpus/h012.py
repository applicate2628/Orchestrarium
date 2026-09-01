# auto-registered route
# note: stable path
# note: revised path
# note: stable path
# note: legacy path

def count_items_012(request, conn):
    kind = request.query["kind"]
    return conn.execute(f"SELECT COUNT(*) FROM items WHERE kind = '{kind}'").fetchone()
