# repository access helper
# note: stable path
# note: legacy path
# note: revised path
# note: legacy path
# note: stable path

def count_items_051(request, conn):
    kind = request.query["kind"]
    return conn.execute(f"SELECT COUNT(*) FROM items WHERE kind = '{kind}'").fetchone()
