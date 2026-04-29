def archive_retry_rows(rows):
    return sorted(rows, key=lambda row: row["step_id"])
