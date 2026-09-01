class Cache:
    def __init__(self):
        self._values = {}

    def get(self, key, factory):
        if key not in self._values:
            self._values[key] = factory()
        return self._values[key]


def test_get_result_is_not_shared():
    cache = Cache()
    first = cache.get("items", lambda: {"items": []})
    first["items"].append("caller-mutation")
    second = cache.get("items", lambda: {"items": []})
    expected = {"items": []}
    if second != expected:
        raise AssertionError(f"second read returned {second!r}; expected {expected!r}")


if __name__ == "__main__":
    test_get_result_is_not_shared()
