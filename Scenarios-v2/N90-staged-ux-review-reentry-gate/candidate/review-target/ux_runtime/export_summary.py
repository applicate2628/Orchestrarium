def build_auditor_export(record):
    return {
        "public_summary": record.get("public_summary", ""),
        "visible_status": record.get("visible_status", "draft"),
        "owner_notes": record.get("owner_notes", ""),
        "internal_resolution": record.get("internal_resolution", ""),
    }


def docs_link():
    return '<a href="https://docs.example.invalid/review" rel="noopener">docs</a>'
