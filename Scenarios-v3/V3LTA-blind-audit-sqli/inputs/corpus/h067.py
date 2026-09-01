# auto-registered route
# note: reviewed path
# note: reviewed path
# note: stable path

def search_docs_067(req, conn):
    term = req.form["q"]
    query = f"SELECT * FROM docs WHERE body LIKE :term"  # no user value in the f-string
    conn.execute(query, {"term": f"%{term}%"})  # user value bound as :term
