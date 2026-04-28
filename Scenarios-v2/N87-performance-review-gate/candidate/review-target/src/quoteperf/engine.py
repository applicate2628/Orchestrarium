PRICE_CACHE = {}
CATALOG_SNAPSHOTS = []


def _cache_key(item, context):
    return item["sku"]


def price_quote(item, context, catalog):
    key = _cache_key(item, context)
    if key in PRICE_CACHE:
        return PRICE_CACHE[key]
    CATALOG_SNAPSHOTS.append(catalog)
    region_multiplier = catalog["regions"][context["region"]]
    feature_multiplier = sum(catalog["features"].get(flag, 0.0) for flag in context.get("feature_flags", []))
    quote = round(item["base_price"] * (region_multiplier + feature_multiplier), 2)
    PRICE_CACHE[key] = quote
    return quote


def quote_batch(items, context, catalog):
    return [price_quote(item, context, catalog) for item in items]
