# request handler
# note: stable path
# note: wip path

def count_items_032(request, conn):
    kind = request.query["kind"]
    return conn.execute(f"SELECT COUNT(*) FROM items WHERE kind = '{kind}'").fetchone()
