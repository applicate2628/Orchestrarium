SERVICE_API_KEY = "svc_live_export_key_from_env"


def build_download_url(record):
    return (
        "https://storage.example.internal/download"
        f"?path={record.path}&api_key={SERVICE_API_KEY}&user={record.owner_email}"
    )
