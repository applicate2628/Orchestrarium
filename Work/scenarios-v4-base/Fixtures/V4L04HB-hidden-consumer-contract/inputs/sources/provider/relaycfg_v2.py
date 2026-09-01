"""relaycfg v2.0 -- in-house configuration client SDK (migration target).

This is the version the platform team ships next release. The changelog in
`inputs/sources/changelog.md` enumerates every change as C01..C10.
"""

from typing import Any, Iterator, Optional, Tuple

_UNSET = object()


class ConfigError(Exception):
    """Base class for all relaycfg errors."""


class MissingKeyError(ConfigError):
    """Raised when a requested key is absent and no default was supplied."""


class RetryableError(ConfigError):
    """Transient failure classes; callers may retry."""


class StaleReadError(ConfigError):
    """Replica returned a stale snapshot for the key.

    C04: in v2 this is a direct ConfigError subclass; it is no longer a
    RetryableError.
    """


_DURATION_SUFFIXES = (("ms", 1), ("s", 1000), ("m", 60000))
_TRUE_WORDS = {"1", "true", "yes", "on"}
_FALSE_WORDS = {"0", "false", "no", "off"}


def _coerce_value(raw: Any) -> Any:
    return raw.strip() if isinstance(raw, str) else raw


def parse_duration_ms(text: Any) -> int:
    """Parse a duration string to integer milliseconds.

    Suffixed forms: '250ms', '30s', '5m'. C03: a bare integer such as '30'
    is interpreted as seconds, matching the platform-wide duration
    convention.
    """
    raw = str(text).strip()
    for suffix, factor in _DURATION_SUFFIXES:
        if raw.endswith(suffix):
            body = raw[: -len(suffix)].strip()
            if not body.isdigit():
                raise ConfigError("invalid duration: %r" % (text,))
            return int(body) * factor
    if raw.isdigit():
        return int(raw) * 1000
    raise ConfigError("invalid duration: %r" % (text,))


class ConfigClient:
    """Layered configuration reader over a parsed file mapping plus an
    environment overlay mapping (already translated to dotted config keys)."""

    def __init__(self, file_values, env_values=None, stale_keys=()):
        self._file = dict(file_values)
        self._env = dict(env_values or {})
        self._stale = frozenset(stale_keys)
        self._backend_reads = 0
        self._cache: dict = {}

    def get(self, key: str, default: Any = _UNSET, *, fresh: bool = False) -> Any:
        """Return the configured value for key.

        C08: the environment overlay wins over the file value.
        C02: an absent key with no supplied default raises MissingKeyError.
        C09: resolved values are memoized per key; pass fresh=True to force
        a backend read.
        """
        if not fresh and key in self._cache:
            return self._cache[key]
        self._backend_reads += 1
        if key in self._env:
            value = _coerce_value(self._env[key])
        elif key in self._file:
            value = _coerce_value(self._file[key])
        else:
            if default is _UNSET:
                raise MissingKeyError(key)
            return default
        self._cache[key] = value
        return value

    def get_int(self, key: str, default: Any = _UNSET, *, fresh: bool = False) -> Optional[int]:
        raw = self.get(key, default, fresh=fresh)
        if raw is None:
            return None
        return int(raw)

    def get_duration_ms(self, key: str, default: Any = _UNSET, *, fresh: bool = False) -> Optional[int]:
        raw = self.get(key, default, fresh=fresh)
        if raw is None:
            return None
        return parse_duration_ms(raw)

    def get_bool(self, key: str, default: Any = _UNSET, *, fresh: bool = False) -> Optional[bool]:
        """C10: new in v2."""
        raw = self.get(key, default, fresh=fresh)
        if isinstance(raw, bool) or raw is None:
            return raw
        text = str(raw).strip().lower()
        if text in _TRUE_WORDS:
            return True
        if text in _FALSE_WORDS:
            return False
        raise ConfigError("invalid boolean: %r" % (raw,))

    def items(self) -> Iterator[Tuple[str, Any]]:
        """Yield (key, value) pairs in sorted key order (C06), with the
        environment overlay winning on collisions (C08)."""
        merged = {**self._file, **self._env}
        for key in sorted(merged):
            yield key, _coerce_value(merged[key])

    def fetch(self, key: str, *, deadline: Optional[float] = None, timeout: Optional[float] = None) -> Any:
        """Read-through accessor against the replica tier.

        C07: the wait bound is now named deadline; timeout is accepted as a
        deprecated alias for this release and maps onto deadline when
        deadline is not given.
        Raises StaleReadError when the replica snapshot for key is stale,
        and MissingKeyError when the key is absent everywhere.
        """
        if deadline is None and timeout is not None:
            deadline = timeout
        self._backend_reads += 1
        if key in self._stale:
            raise StaleReadError(key)
        if key in self._env:
            return _coerce_value(self._env[key])
        if key in self._file:
            return _coerce_value(self._file[key])
        raise MissingKeyError(key)

    def backend_read_count(self) -> int:
        """Number of backend reads performed by this client instance.

        Audit metering pipelines consume this counter. C09: cache hits do
        not perform a backend read.
        """
        return self._backend_reads
