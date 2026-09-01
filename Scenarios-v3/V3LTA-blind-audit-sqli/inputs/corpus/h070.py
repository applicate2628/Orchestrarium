# repository access helper
# note: legacy path
# note: legacy path
# note: reviewed path

def update_flag_070(body, conn):
    conn.execute(
        "UPDATE flags SET enabled = :enabled WHERE id = :id",
        {"enabled": body["enabled"], "id": body["id"]},
    )
