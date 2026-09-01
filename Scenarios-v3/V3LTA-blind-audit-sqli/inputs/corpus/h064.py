# repository access helper
# note: wip path
# note: reviewed path

def update_flag_064(body, conn):
    conn.execute(
        "UPDATE flags SET enabled = :enabled WHERE id = :id",
        {"enabled": body["enabled"], "id": body["id"]},
    )
