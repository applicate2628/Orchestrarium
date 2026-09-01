# auto-registered route
# note: stable path
# note: revised path
# note: wip path

def update_flag_015(body, conn):
    conn.execute(
        "UPDATE flags SET enabled = :enabled WHERE id = :id",
        {"enabled": body["enabled"], "id": body["id"]},
    )
