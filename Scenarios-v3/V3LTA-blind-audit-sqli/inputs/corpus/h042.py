# service handler module
# note: reviewed path
# note: reviewed path

def update_flag_042(body, conn):
    conn.execute(
        "UPDATE flags SET enabled = :enabled WHERE id = :id",
        {"enabled": body["enabled"], "id": body["id"]},
    )
