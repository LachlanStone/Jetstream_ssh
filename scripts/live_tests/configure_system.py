import json
import sys
from ansible_collections.lachlanstone.jetstream.plugins.modules.jetstream_system import run_module as _ansible_run_modules


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
params = {
    "host": "192.0.2.10",
    "port": 22,
    "username": "admin",
    "password": "password",
    "enable_password": "password",
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
