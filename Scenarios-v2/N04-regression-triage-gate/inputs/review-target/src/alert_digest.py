from hashlib import sha1


def build_digest_key(channel: str, report: dict[str, object]) -> str:
    generated_at_minute = str(report["generated_at"])[:16]
    digest_source = f"{channel}:{generated_at_minute}:{report['summary']}"
    return sha1(digest_source.encode("utf-8")).hexdigest()[:12]
