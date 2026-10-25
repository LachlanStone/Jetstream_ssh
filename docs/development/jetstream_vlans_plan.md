# Implementation Plan: `jetstream_vlans` Module

> **Status:** implemented in 1.1.0. For extending the module, see
> [`adding_vlan_components.md`](adding_vlan_components.md). This document is the
> original design plan and is kept for history.

This document is written for an implementation agent picking up this task cold.
Read it fully before touching any file.

---

## Repository layout — new files to create

```
plugins/
  modules/
    jetstream_vlans.py              # Ansible module entry point (new)
  module_utils/
    vlans/
      __init__.py                   # empty, marks package (new)
      vlan_builder.py               # pure command builder — no Ansible, no Netmiko (new)
```

Existing files **not touched** by this module:
- `plugins/module_utils/send_command.py` — used as-is
- `plugins/module_utils/collector.py` — used as-is
- `plugins/module_utils/device.py` — used as-is
- `plugins/modules/jetstream_interfaces.py` — unchanged
- `plugins/module_utils/interfaces/interface_builder.py` — unchanged

---

## Two-file contract

Identical pattern to `jetstream_interfaces`:

1. **`vlan_builder.py`** — pure command builder, no side effects, no imports of Ansible or Netmiko.
2. **`jetstream_vlans.py`** — Ansible module entry point, argument_spec, SSH orchestration.

---

## `vlan_builder.py`

### Function: `build_vlan_commands(vlan)`

**Signature:**
```python
def build_vlan_commands(vlan: dict) -> list[str]:
```

**Argument:** one element from `module.params["vlans"]`.

Required key: `vlan_id`
Optional keys: `name`, `ip_address`, `subnet_mask`, `ip_dhcp`

**Returns:** flat `list[str]` of CLI commands in switch-expected order, with `exit` as the final command of each context block.

**Command order and logic:**

```
# Step 1 — enter VLAN database context and create/select the VLAN
vlan <vlan_id>

# Step 2 — set name (only when name is provided)
name <name>

# Step 3 — exit VLAN database context
exit

# Step 4 — enter SVI context (only when ip_address or ip_dhcp is provided)
interface vlan <vlan_id>

# Step 5a — assign static IP (only when ip_address and subnet_mask are provided and ip_dhcp is falsy)
ip address <ip_address> <subnet_mask>

# Step 5b — assign DHCP (only when ip_dhcp is True; mutually exclusive with ip_address)
ip address-alloc dhcp

# Step 6 — exit SVI context (only emitted when step 4 was entered)
exit
```

**Skip rules (idempotency-friendly):**
- `name`: skip command when value is `None`.
- SVI block (`interface vlan ...` through its `exit`): skip entirely when both `ip_address` and `ip_dhcp` are falsy.
- `ip address`: skip when `ip_address` is `None` or `subnet_mask` is `None`.
- `ip address-alloc dhcp`: skip when `ip_dhcp` is `False` or `None`.

**Validation (raise `ValueError`):**
- `vlan_id` not in range 1–4094.
- Both `ip_address` and `ip_dhcp` are set simultaneously (mutually exclusive).
- `ip_address` is set but `subnet_mask` is missing.

**Invariants:**
- No Ansible imports. No Netmiko imports. Importable with plain Python.
- Same input always produces same output.
- `exit` always terminates each entered context block.
- A field at its default value must not emit a CLI command.

**Example — VLAN with name and static SVI:**
```python
build_vlan_commands({
    "vlan_id": 10,
    "name": "Servers",
    "ip_address": "192.168.10.1",
    "subnet_mask": "255.255.255.0",
    "ip_dhcp": False,
})
# Returns:
# ["vlan 10", "name Servers", "exit", "interface vlan 10", "ip address 192.168.10.1 255.255.255.0", "exit"]
```

**Example — VLAN with name, no SVI:**
```python
build_vlan_commands({
    "vlan_id": 20,
    "name": "Clients",
    "ip_address": None,
    "subnet_mask": None,
    "ip_dhcp": False,
})
# Returns:
# ["vlan 20", "name Clients", "exit"]
```

**Example — VLAN with DHCP SVI:**
```python
build_vlan_commands({
    "vlan_id": 30,
    "name": None,
    "ip_address": None,
    "subnet_mask": None,
    "ip_dhcp": True,
})
# Returns:
# ["vlan 30", "exit", "interface vlan 30", "ip address-alloc dhcp", "exit"]
```

**Example — VLAN only, no name, no SVI:**
```python
build_vlan_commands({
    "vlan_id": 40,
    "name": None,
    "ip_address": None,
    "subnet_mask": None,
    "ip_dhcp": False,
})
# Returns:
# ["vlan 40", "exit"]
```

---

## `jetstream_vlans.py`

### Argument spec

Top-level connection params mirror `jetstream_interfaces.py` exactly:

```python
"host":            {"type": "str",  "required": True},
"port":            {"type": "int",  "default": 22},
"username":        {"type": "str",  "required": True},
"password":        {"type": "str",  "no_log": True,  "default": ""},
"enable_password": {"type": "str",  "no_log": True,  "default": ""},
```

VLAN list param:

```python
"vlans": {
    "type": "list",
    "elements": "dict",
    "required": True,
    "options": {
        "vlan_id": {
            "type": "int",
            "required": True,
        },
        "name": {
            "type": "str",
            "required": False,
            "default": None,
        },
        "ip_address": {
            "type": "str",
            "required": False,
            "default": None,
        },
        "subnet_mask": {
            "type": "str",
            "required": False,
            "default": None,
        },
        "ip_dhcp": {
            "type": "bool",
            "required": False,
            "default": False,
        },
    },
},
```

`required: True` only on `vlan_id`. All other fields have defaults so existing playbooks do not break.

### `configure_vlan()` function

Pattern identical to `configure_interface()` in `jetstream_interfaces.py`:

```python
def configure_vlan(net_connect, vlan, collector, check_mode):
    vlan_id = vlan["vlan_id"]
    cmds = build_vlan_commands(vlan)

    if check_mode:
        collector.add_step(
            name=f"configure_vlan:{vlan_id}",
            step_result={
                "changed": False,
                "msg": f"VLAN {vlan_id}: would apply {len(cmds)} command(s).",
                "commands": cmds,
                "settings": {k: v for k, v in vlan.items() if k != "vlan_id"},
                "stdout": "",
            },
        )
        return

    stdout_parts = []
    for cmd in cmds:
        if cmd == "exit":
            output = net_connect.send_command_timing(cmd)
        else:
            output = send_command(net_connect, cmd, expect_string=_CONFIG_PROMPT)
        stdout_parts.append(f"# {cmd}\n{output}".strip())

    collector.add_step(
        name=f"configure_vlan:{vlan_id}",
        step_result={
            "changed": True,
            "msg": f"VLAN {vlan_id} configured.",
            "commands": cmds,
            "commands_sent": cmds,
            "settings": {k: v for k, v in vlan.items() if k != "vlan_id"},
            "stdout": "\n".join(stdout_parts),
        },
    )
```

### `run_module()` function

```python
def run_module(module):
    device = build_device(module)
    collector = ResultCollector()
    collector.set_basic_info(
        switch=module.params["host"],
        check_mode=module.check_mode,
        verbosity=module._verbosity,
    )

    vlans = module.params.get("vlans") or []

    with ConnectHandler(**device) as net_connect:
        net_connect.enable()
        net_connect.config_mode()
        for vlan in vlans:
            configure_vlan(net_connect, vlan, collector, module.check_mode)

    result = collector.return_info()
    module.exit_json(**result)
```

### `_CONFIG_PROMPT` regex

Same as interfaces module:
```python
_CONFIG_PROMPT = r"\(config[^)]*\)#"
```

This matches both `(config)#` and context-specific prompts like `(config-vlan)#` and `(config-if)#`.

### Imports

```python
#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type

import logging
from ansible.module_utils.basic import AnsibleModule
from netmiko import ConnectHandler
from plugins.module_utils.send_command import send_command
from plugins.module_utils.collector import ResultCollector
from plugins.module_utils.vlans.vlan_builder import build_vlan_commands
from plugins.module_utils.device import build_device
```

---

## Smoke test (no real switch needed)

Run from the repo root after creating the files:

```python
import sys
sys.path.insert(0, ".")
from plugins.module_utils.vlans.vlan_builder import build_vlan_commands

# Case 1: VLAN with name + static SVI
cmds = build_vlan_commands({
    "vlan_id": 10, "name": "Servers",
    "ip_address": "192.168.10.1", "subnet_mask": "255.255.255.0", "ip_dhcp": False,
})
assert cmds == ["vlan 10", "name Servers", "exit", "interface vlan 10", "ip address 192.168.10.1 255.255.255.0", "exit"], cmds

# Case 2: VLAN with name, no SVI
cmds = build_vlan_commands({
    "vlan_id": 20, "name": "Clients",
    "ip_address": None, "subnet_mask": None, "ip_dhcp": False,
})
assert cmds == ["vlan 20", "name Clients", "exit"], cmds

# Case 3: VLAN with DHCP SVI, no name
cmds = build_vlan_commands({
    "vlan_id": 30, "name": None,
    "ip_address": None, "subnet_mask": None, "ip_dhcp": True,
})
assert cmds == ["vlan 30", "exit", "interface vlan 30", "ip address-alloc dhcp", "exit"], cmds

# Case 4: bare VLAN, no name, no SVI
cmds = build_vlan_commands({
    "vlan_id": 40, "name": None,
    "ip_address": None, "subnet_mask": None, "ip_dhcp": False,
})
assert cmds == ["vlan 40", "exit"], cmds

print("All assertions passed.")
```

Verify the module parses cleanly:
```bash
python3 -c "import ast, pathlib; ast.parse(pathlib.Path('plugins/modules/jetstream_vlans.py').read_text()); print('OK')"
```

---

## Invariants — never break these

- `build_vlan_commands` has no side effects. Same input → same output.
- A field at its default value must not emit a CLI command.
- Every entered context block (`vlan <id>`, `interface vlan <id>`) must be closed with `exit`.
- No field in `argument_spec` may be `required: True` except `vlan_id`.
- `build_vlan_commands` must be importable with plain Python (no Ansible, no Netmiko).

---

## Known limits

- **No idempotency.** Module always pushes commands. No `show vlan` read before writing.
- **No `state: absent`.** Deleting a VLAN or removing an SVI IP requires `no vlan <id>` / `no ip address` — not implemented. Add a `state` param and `build_absent_commands` if needed later.
- **No SVI `no shutdown`.** SVI interfaces on JetStream come up automatically when the VLAN exists; no explicit `no shutdown` needed. If a specific firmware requires it, add an `svi_enabled` bool field.
- **subnet_mask is dotted-decimal only.** CIDR prefix notation (e.g. `/24`) is not handled; the CLI expects dotted-decimal.
