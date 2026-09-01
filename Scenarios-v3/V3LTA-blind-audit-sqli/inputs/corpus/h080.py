# internal endpoint
# note: stable path
# note: revised path
# note: stable path
# note: stable path
# note: reviewed path

def count_items_080(request, conn):
    kind = request.query["kind"]
    return conn.execute(f"SELECT COUNT(*) FROM items WHERE kind = '{kind}'").fetchone()
