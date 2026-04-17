from __future__ import annotations


def build_view_state(rows, selected_id):
    visible_ids = [row["id"] for row in rows]
    chosen = selected_id if selected_id is not None else (visible_ids[0] if visible_ids else None)
    detail_id = selected_id
    return {
        "visible_ids": visible_ids,
        "selected_id": chosen,
        "detail_id": detail_id,
    }
