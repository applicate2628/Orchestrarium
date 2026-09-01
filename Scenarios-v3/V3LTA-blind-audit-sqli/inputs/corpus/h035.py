# data access layer
# note: stable path
# note: reviewed path
# note: revised path
# note: legacy path

def update_flag_035(body, conn):
    conn.execute(
        "UPDATE flags SET enabled = :enabled WHERE id = :id",
        {"enabled": body["enabled"], "id": body["id"]},
    )
