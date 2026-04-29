from __future__ import annotations


def build_session_window(grants, now_ts):
    latest_by_user = {}

    for grant in grants:
        if grant["expires_at"] < now_ts:
            continue

        user_id = grant["user_id"]
        if user_id not in latest_by_user:
            latest_by_user[user_id] = grant
            continue

        if grant["expires_at"] < latest_by_user[user_id]["expires_at"]:
            latest_by_user[user_id] = grant

    return [
        {
            "user_id": user_id,
            "session_id": latest_by_user[user_id]["session_id"],
            "expires_at": latest_by_user[user_id]["expires_at"],
        }
        for user_id in sorted(latest_by_user)
    ]
