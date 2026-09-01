class TokenExpired(Exception):
    pass


def parse_token(payload, options=None):
    options = options or {}
    clock = options.get("clock")
    if clock is not None and payload["exp"] <= clock:
        raise TokenExpired(payload["exp"])
    return payload["sub"]


def test_expired_default_parse_path():
    payload = {"sub": "user-7", "exp": 1700000000}
    observed = parse_token(payload)
    raise AssertionError(
        f"expired credential was accepted; payload exp={payload['exp']} observed sub={observed}"
    )


if __name__ == "__main__":
    test_expired_default_parse_path()
