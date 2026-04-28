CATALOG = {
    "regions": {
        "us": 1.00,
        "eu": 1.20,
        "apac": 1.35
    },
    "features": {
        "priority": 0.10,
        "regulated": 0.18,
        "bulk": -0.05
    }
}


def refresh_catalog(new_catalog):
    CATALOG.clear()
    CATALOG.update(new_catalog)
    return CATALOG
