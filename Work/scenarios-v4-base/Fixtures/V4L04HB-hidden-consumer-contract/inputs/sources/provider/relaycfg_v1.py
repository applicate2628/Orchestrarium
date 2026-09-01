"""relaycfg v1.9 -- in-house configuration client SDK (pre-migration snapshot).

This is the version every registered downstream consumer runs today.
"""


class ConfigError(Exception):
    """Base class for all relaycfg errors."""


class MissingKeyError(ConfigError):
    """Raised by read-through accessors when a key is absent everywhere."""


class RetryableError(ConfigError):
    """Transient failure classes; callers may retry."""


class StaleReadError(RetryableError):
    """Replica returned a stale snapshot for the key."""


_DURATION_SUFFIXES = (("ms", 1), ("s", 1000), ("m", 60000))


def _coerce(raw):
    return raw.strip() if isinstance(raw, str) else raw


def parse_duration_ms(text):
    """Parse a duration string to integer milliseconds.

    Suffixed forms: '250ms', '30s', '5m'. A bare integer such as '250' is
    interpreted as milliseconds.
    """
    raw = str(text).strip()
    for suffix, factor in _DURATION_SUFFIXES:
        if raw.endswith(suffix):
            body = raw[: -len(suffix)].strip()
            if not body.isdigit():
                raise ConfigError("invalid duration: %r" % (text,))
            return int(body) * factor
    if raw.isdigit():
        return int(raw)
    raise ConfigError("invalid duration: %r" % (text,))


class ConfigClient:
    """Layered configuration reader over a parsed file mapping plus an
    environment overlay mapping (already translated to dotted config keys)."""

    def __init__(self, file_values, env_values=None, stale_keys=()):
        self._file = dict(file_values)
        self._env = dict(env_values or {})
        self._stale = frozenset(stale_keys)
        self._backend_reads = 0

    def get(self, key, default=None):
        """Return the configured value for key.

        Precedence: the file value wins over the environment overlay.
        An absent key returns default, which is None when not supplied.
        Every call performs one backend read.
        """
        self._backend_reads += 1
        if key in self._file:
            return _coerce(self._file[key])
        if key in self._env:
            return _coerce(self._env[key])
        return default

    def get_int(self, key, default=None):
        raw = self.get(key, default)
        if raw is None:
            return None
        return int(raw)

    def get_duration_ms(self, key, default=None):
        raw = self.get(key, default)
        if raw is None:
            return None
        return parse_duration_ms(raw)

    def items(self):
        """Yield (key, value) pairs: file entries in file order first, then
        overlay-only entries in overlay order."""
        seen = set()
        for key, value in self._file.items():
            seen.add(key)
            yield key, _coerce(value)
        for key, value in self._env.items():
            if key not in seen:
                yield key, _coerce(value)

    def fetch(self, key, *, timeout=None):
        """Read-through accessor against the replica tier.

        Raises StaleReadError when the replica snapshot for key is stale,
        and MissingKeyError when the key is absent everywhere. The timeout
        argument bounds the replica wait; None means the client default.
        """
        self._backend_reads += 1
        if key in self._stale:
            raise StaleReadError(key)
        if key in self._file:
            return _coerce(self._file[key])
        if key in self._env:
            return _coerce(self._env[key])
        raise MissingKeyError(key)

    def backend_read_count(self):
        """Number of backend reads performed by this client instance.

        Audit metering pipelines consume this counter.
        """
        return self._backend_reads
