import argparse
import json
import logging
import os
import sys

# Make the collection root importable when this script is run directly.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from ansible_collections.lachlanstone.jetstream.plugins.modules.jetstream_system import run_module as _ansible_run_modules


def build_parser():
    parser = argparse.ArgumentParser(description="Live test for jetstream_system")
    parser.add_argument("--host", default=os.environ.get("JETSTREAM_HOST", "192.0.2.10"), help="Switch IP or hostname")
    parser.add_argument("--username", default=os.environ.get("JETSTREAM_USERNAME", "admin"), help="SSH username")
    parser.add_argument("--password", default=os.environ.get("JETSTREAM_PASSWORD", "password"), help="SSH password")
    parser.add_argument("--enable-password", default=os.environ.get("JETSTREAM_ENABLE_PASSWORD", "password"), help="Enable password")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging to the terminal")
    return parser


class FakeModule:
    """
    Lightweight wrapper that emulates AnsibleModule's interface.
    Acts as a dict (for subscript access) AND exposes .params for attribute access.
    """
    def __init__(self, params):
        self.params = params
        self.params.setdefault("_verbosity", 0)
        self._verbosity = 3
        self.check_mode = False
        self._last_exit = None

    # --- Make it subscriptable like a dict: obj["key"] ---
    def __getitem__(self, key):
        return self.params[key]

    def __setitem__(self, key, value):
        self.params[key] = value

    def __contains__(self, key):
        return key in self.params

    def get(self, key, default=None):
        return self.params.get(key, default)

    # --- AnsibleModule methods ---
    def exit_json(self, **kwargs):
        kwargs["changed"] = kwargs.get("changed", False)
        self._last_exit = kwargs
        raise SystemExit(0)

    def fail_json(self, msg, **kwargs):
        raise RuntimeError(f"Module failed: {msg}")


def run_module_with_params(params):
    """
    Run the Ansible module logic with a plain params dict.
    Returns the result dictionary.
    """
    fake_module = FakeModule(params)
    try:
        _ansible_run_modules(fake_module)
    except SystemExit as exc:
        if exc.code in (None, 0):
            return fake_module._last_exit or {}
        raise
    return fake_module._last_exit or {}


# --- Your params dict ---
args = build_parser().parse_args()

if args.verbose:
    logging.basicConfig(
        level=logging.DEBUG,
        stream=sys.stdout,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    netmiko_logger = logging.getLogger("netmiko")
    netmiko_logger.setLevel(logging.DEBUG)
    netmiko_logger.propagate = True

params = {
    "host": args.host,
    "port": 22,
    "username": args.username,
    "password": args.password,
    "enable_password": args.enable_password,
    "system": {
        "hostname": "NewHostname",
        "location": "NewLocation",
        "contact": "NewContact"
    }
}


# --- Run the module ---
try:
    results = run_module_with_params(params)
    print(json.dumps(results, indent=2))
except RuntimeError as e:
    print(json.dumps({"failed": True, "msg": str(e)}, indent=2))
    sys.exit(1)
