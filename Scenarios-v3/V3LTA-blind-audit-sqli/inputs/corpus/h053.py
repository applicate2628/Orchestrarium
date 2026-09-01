# request handler

def search_docs_053(req, conn):
    term = req.form["q"]
    query = f"SELECT * FROM docs WHERE body LIKE :term"  # no user value in the f-string
    conn.execute(query, {"term": f"%{term}%"})  # user value bound as :term
