from __future__ import annotations

# ---------------------------------------------------------------------------
# Shared connection argument spec
# ---------------------------------------------------------------------------
# Every JetStream module connects to the switch with the same six options.
# They used to be copied into each module's ``main()`` and have already
# drifted; define them once here and compose them into each module spec.
#
# Example:
#     argument_spec = {}
#     argument_spec.update(CONNECTION_ARGS)
#     argument_spec.update({...module-specific options...})
CONNECTION_ARGS = {
    "host": {"type": "str", "required": True},
    "port": {"type": "int", "default": 22},
    "username": {"type": "str", "required": True},
    "password": {"type": "str", "no_log": True, "default": ""},
    "enable_password": {"type": "str", "no_log": True, "default": ""},
    "read_timeout": {"type": "float", "required": False},
}


def connection_argument_spec() -> dict:
    """Return a copy of the shared connection argument spec."""
    return dict(CONNECTION_ARGS)


# ---------------------------------------------------------------------------
# Documentation fragment for the shared connection options
# ---------------------------------------------------------------------------
# Modules include this under their ``options:`` key so published docs stay in
# sync with CONNECTION_ARGS:
#
#     DOCUMENTATION = r"""
#     ---
#     module: jetstream_acls
#     ...
#     options:
#     """ + CONNECTION_DOCUMENTATION + r"""
#       acls:
#         ...
#     """
CONNECTION_DOCUMENTATION = r"""
  host:
    description: Hostname or IP address of the switch.
    type: str
    required: true
  port:
    description: SSH port of the switch.
    type: int
    default: 22
  username:
    description: SSH username.
    type: str
    required: true
  password:
    description: SSH password.
    type: str
    default: ""
  enable_password:
    description: Password for privileged (enable) mode.
    type: str
    default: ""
  read_timeout:
    description:
      - Seconds Netmiko waits for the command prompt before raising a read timeout.
      - Defaults to C(JETSTREAM_READ_TIMEOUT) when set, otherwise 30.
    type: float
"""
