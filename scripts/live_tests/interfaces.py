import json
import sys
from ansible_collections.lachlanstone.jetstream.plugins.modules.jetstream_interfaces import (
    run_module as _ansible_run_module,
)

# True: report commands only, nothing is sent. False: push config to the real switch.
CHECK_MODE = False

PORTS = ["1/0/9", "1/0/10", "1/0/11"]


class FakeModule:
    """
    Lightweight wrapper that emulates AnsibleModule's interface.
    Acts as a dict (for subscript access) AND exposes .params for attribute access.
    """

    def __init__(self, params, check_mode=False):
        self.params = params
        self.params.setdefault("_verbosity", 0)
        self._verbosity = 3
        self.check_mode = check_mode
        self._last_exit = None

    def __getitem__(self, key):
        return self.params[key]

    def __setitem__(self, key, value):
        self.params[key] = value

    def __contains__(self, key):
        return key in self.params

    def get(self, key, default=None):
        return self.params.get(key, default)

    def exit_json(self, **kwargs):
        kwargs["changed"] = kwargs.get("changed", False)
        self._last_exit = kwargs
        raise SystemExit(0)

    def fail_json(self, msg, **kwargs):
        raise RuntimeError(f"Module failed: {msg}")


def run_module_with_params(params, check_mode=False):
    """Run the Ansible module logic with a plain params dict. Returns the result dict."""
    fake_module = FakeModule(params, check_mode)
    try:
        _ansible_run_module(fake_module)
    except SystemExit as exc:
        if exc.code in (None, 0):
            return fake_module._last_exit or {}
        raise
    return fake_module._last_exit or {}


params = {
    "host": "192.0.2.10",
    "port": 22,
    "username": "admin",
    "password": "password",
    "enable_password": "password",
    "interfaces": [
        {
            "name": port,
            "port_type": "two-gigabitEthernet",
            "vlans_tagged": [20],
            "vlans_disabled": [10],
        }
        for port in PORTS
    ],
}


def check_results(results):
    """Assert the result matches the expected per-interface behavior."""
    steps = results.get("steps", [])
    assert len(steps) == len(PORTS), f"expected {len(PORTS)} steps, got {len(steps)}"
    for port, step in zip(PORTS, steps):
        assert step["name"] == f"configure_interface:{port}", step["name"]
        cmds = step.get("commands") or []
        assert "switchport general allowed vlan 20 tagged" in cmds, cmds
        assert "no switchport general allowed vlan 10" in cmds, cmds
        assert step["changed"] is (not CHECK_MODE), f"{port}: changed={step['changed']}"


try:
    results = run_module_with_params(params, CHECK_MODE)
    print(json.dumps(results, indent=2))
    check_results(results)
except (RuntimeError, AssertionError) as e:
    print(json.dumps({"failed": True, "msg": str(e)}, indent=2))
    sys.exit(1)
