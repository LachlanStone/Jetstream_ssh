# Collection Module SPEC

Standards for new (and refactored) modules in `lachlanstone.jetstream`.
Derived from what the existing modules share. Follow this when adding a module
or changing connection, check-mode, or result behaviour.

Canonical helpers:

- `plugins/module_utils/device.py` — `build_device()`
- `plugins/module_utils/collector.py` — `ResultCollector`

---

## Required parameters

Every module's `argument_spec` must include:

| Parameter | Type | Required | Default | Notes |
|---|---|---|---|---|
| `host` | `str` | yes | — | Switch hostname or IP |
| `port` | `int` | no | `22` | SSH port |
| `username` | `str` | yes | — | SSH username |
| `password` | `str` | no | `""` | `no_log: true` |
| `enable_password` | `str` | no | `""` | `no_log: true` |
| `read_timeout` | `float` | no | unset | Falls back to `JETSTREAM_READ_TIMEOUT`, then `30` |

```python
argument_spec={
    "host": {"type": "str", "required": True},
    "port": {"type": "int", "default": 22},
    "username": {"type": "str", "required": True},
    "password": {"type": "str", "no_log": True, "default": ""},
    "enable_password": {"type": "str", "no_log": True, "default": ""},
    "read_timeout": {"type": "float", "required": False},
    # ... module-specific options ...
}
```

---

## Connection pattern

1. Build the Netmiko device dict with `build_device(module)`.
2. Open the session with `with ConnectHandler(**device) as net_connect:`.
3. Call `net_connect.enable()` before any privileged / config work.
4. Call `net_connect.config_mode()` when config commands are needed.

```python
from netmiko import ConnectHandler
from ansible_collections.lachlanstone.jetstream.plugins.module_utils.device import (
    build_device,
)

device = build_device(module)

with ConnectHandler(**device) as net_connect:
    net_connect.enable()
    net_connect.config_mode()  # when config commands are needed
    # ... module work ...
```

Do not hand-roll connection dicts. `build_device()` owns `device_type`,
`secret` ← `enable_password`, and `read_timeout_override`.

---

## Result pattern

Use `ResultCollector` for all step recording. Helpers append steps and return;
only `main()` / `run_module()` call `module.exit_json()` or `module.fail_json()`.

1. Create the collector and call `set_basic_info` at the start of the run.
2. Each logical operation = one `collector.add_step(name, step_result)`.
3. Finish with `result = collector.return_info()` then `module.exit_json(**result)`.
4. On failure: `module.fail_json(**result)` (or with a collector-backed result).

```python
from ansible_collections.lachlanstone.jetstream.plugins.module_utils.collector import (
    ResultCollector,
)

collector = ResultCollector()
collector.set_basic_info(
    switch=module.params["host"],
    check_mode=module.check_mode,
    verbosity=module._verbosity,
)

# ... operations that call collector.add_step(...) ...

result = collector.return_info()
module.exit_json(**result)
```

### Step result contract

Every `step_result` passed to `add_step` must include:

| Field | Meaning |
|---|---|
| `changed` | Whether this step changed (or would change) state |
| `msg` | Human-readable step summary |
| `commands` | Commands built for this step |
| `commands_sent` | Commands actually sent; **empty list in check mode** |

```python
collector.add_step(
    "configure_example",
    {
        "changed": changed,
        "msg": "Configured example",
        "commands": commands,
        "commands_sent": [] if check_mode else commands,
    },
)
```

---

## Return schema contract

Every module must return at least:

| Field | Type | Source |
|---|---|---|
| `msg` | `str` | Last / aggregate message |
| `switch` | `str` | Host from `set_basic_info` |
| `changed` | `bool` | Aggregated from steps |
| `check_mode` | `bool` | From `set_basic_info` |
| `cmd` | `str` | Last command recorded as sent |
| `steps` | `list` | Per-step records from the collector |

Produce this via `collector.return_info()` — do not assemble a parallel result dict.

---

## Check mode

- All **config** modules must declare `supports_check_mode=True`.
- In check mode: build commands, record them on the step (`commands`), set
  `changed: False`, keep `commands_sent: []`, and **do not** send to the device.
- `jetstream_command` is the only module that explicitly does **not** support
  check mode (`supports_check_mode=False`).

```python
module = AnsibleModule(
    argument_spec=argument_spec,
    supports_check_mode=True,  # False only for jetstream_command
)
```

---

## Minimal module skeleton

```python
from ansible.module_utils.basic import AnsibleModule
from netmiko import ConnectHandler

from ansible_collections.lachlanstone.jetstream.plugins.module_utils.collector import (
    ResultCollector,
)
from ansible_collections.lachlanstone.jetstream.plugins.module_utils.device import (
    build_device,
)


def run_module(module):
    device = build_device(module)
    collector = ResultCollector()
    collector.set_basic_info(
        switch=module.params["host"],
        check_mode=module.check_mode,
        verbosity=module._verbosity,
    )

    with ConnectHandler(**device) as net_connect:
        net_connect.enable()
        net_connect.config_mode()
        # call helpers that each collector.add_step(...)

    result = collector.return_info()
    if collector.failed:
        module.fail_json(**result)
    module.exit_json(**result)


def main():
    module = AnsibleModule(
        argument_spec={
            "host": {"type": "str", "required": True},
            "port": {"type": "int", "default": 22},
            "username": {"type": "str", "required": True},
            "password": {"type": "str", "no_log": True, "default": ""},
            "enable_password": {"type": "str", "no_log": True, "default": ""},
            "read_timeout": {"type": "float", "required": False},
        },
        supports_check_mode=True,
    )
    try:
        run_module(module)
    except Exception as e:
        module.fail_json(msg=str(e), exception=e, check_mode=module.check_mode)
```

---

## Related docs

Per-module extension guides (field schemas, builders, invariants):

- [adding_system_components.md](adding_system_components.md)
- [adding_interface_components.md](adding_interface_components.md)
- [adding_vlan_components.md](adding_vlan_components.md)
- [adding_acls_components.md](adding_acls_components.md)
