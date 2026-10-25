import os

DEFAULT_READ_TIMEOUT = 30.0
READ_TIMEOUT_ENV = "JETSTREAM_READ_TIMEOUT"


def _positive_timeout(value, source):
    try:
        timeout = float(value)
    except (TypeError, ValueError):
        timeout = 0
    if timeout <= 0:
        raise ValueError(
            f"{source} must be a positive number of seconds, got {value!r}"
        )
    return timeout


def read_timeout_override(params=None):
    """Return the connection-wide Netmiko read timeout, in seconds.

    Netmiko applies this to every ``send_command`` call on the connection,
    overriding both its own default and any per-call ``read_timeout``.
    The module's ``read_timeout`` option wins; otherwise
    ``JETSTREAM_READ_TIMEOUT`` is used, then 30 seconds.
    """
    params = params or {}
    if params.get("read_timeout") is not None:
        return _positive_timeout(params["read_timeout"], "read_timeout")
    raw = os.environ.get(READ_TIMEOUT_ENV)
    if raw is None:
        return DEFAULT_READ_TIMEOUT
    return _positive_timeout(raw, READ_TIMEOUT_ENV)


def build_device(module):
    """Build a Netmiko device dict from Ansible module params."""
    params = getattr(module, "params", module)
    return {
        "device_type": "tplink_jetstream",
        "host": params["host"],
        "port": params["port"],
        "username": params["username"],
        "password": params["password"],
        "secret": params["enable_password"],
        "read_timeout_override": read_timeout_override(params),
    }
