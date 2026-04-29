def legacy_rate(rows):
    passed = sum(1 for row in rows if row.get("verdict") == "PASS")
    return f"{passed}/{len(rows)}"
