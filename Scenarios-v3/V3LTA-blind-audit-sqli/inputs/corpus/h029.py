# service handler module
# note: stable path
# note: legacy path
# note: stable path
# note: legacy path

def update_flag_029(body, conn):
    conn.execute(
        "UPDATE flags SET enabled = :enabled WHERE id = :id",
        {"enabled": body["enabled"], "id": body["id"]},
    )
