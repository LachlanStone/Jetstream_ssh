class FakeModule:
    """Lightweight wrapper that emulates AnsibleModule's interface."""

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
