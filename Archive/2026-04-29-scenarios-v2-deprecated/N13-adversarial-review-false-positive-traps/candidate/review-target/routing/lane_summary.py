def summarize_lane(rows):
    scoreable = [row for row in rows if row["status"] in ("pass", "fail")]
    passed = len([row for row in scoreable if row["status"] == "pass"])
    return f"{passed}/{len(rows)}"


def status_label(row):
    if row["status"] == "timeout" and row.get("artifact_verifier") == "pass":
        return "PASS"
    return row["status"].upper()
