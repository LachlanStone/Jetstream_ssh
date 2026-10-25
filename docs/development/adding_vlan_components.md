# Adding Components to `jetstream_vlans`

This document is written for a future AI agent or developer picking up this module cold.
Read it fully before touching any file.

---

## Repository layout (relevant paths)

```
plugins/
  modules/
    jetstream_vlans.py                   # Ansible module entry point
  module_utils/
    vlans/
      __init__.py                        # empty, marks package
      vlan_builder.py                    # pure command builder — no Ansible, no Netmiko
    config_mode.py                       # prompt-based CLI mode detection/guards
    send_command.py                      # sends one CLI command over Netmiko
    collector.py                         # ResultCollector: accumulates per-step results
    device.py                            # builds the Netmiko device dict
tests/
  unit/test_jetstream_vlans.py           # builder + module unit tests
  live_tests/vlans.py                    # live switch test
```

Every new VLAN parameter touches exactly **two files**:

1. `vlan_builder.py` — what CLI commands to emit
2. `jetstream_vlans.py` — what YAML the user is allowed to write

`configure_vlan()` calls `build_vlan_commands()` and iterates the result; you do
not touch that function for a new field.

---

## The two-file contract

### `vlan_builder.py` — `build_vlan_commands(vlan)`

`vlan` is a plain dict (one element from `module.params["vlans"]`). The function
returns a flat `list[str]` in the order the switch expects, with `exit` closing
each context it opens.

**Current command order:**

```
vlan <vlan_id>
name <name>                 # only when name is not None
exit

interface vlan <vlan_id>    # only when ip_address or ip_dhcp is set
ip address <ip> <mask>      # static only
ip address-alloc dhcp       # DHCP only
exit
```

**Rules for adding a command here:**

- Read the value with `.get("your_field")`.
- Skip the command entirely when the value is `None` or equals the switch default.
- Append the command inside the correct context block.
- Close every entered context with `exit`.
- Raise `ValueError` only for invalid values or combinations that `choices`
  cannot catch.
- No Ansible imports. No Netmiko imports. The builder must be importable and
  testable with plain Python.

**Validation currently enforced:**

| Condition | Result |
|---|---|
| `vlan_id` outside 1–4094 | `ValueError` |
| `ip_address` and `ip_dhcp` both set | `ValueError` |
| `ip_address` set without `subnet_mask` | `ValueError` |

### `jetstream_vlans.py` — `main()` → `argument_spec`

The VLAN list element lives under `argument_spec["vlans"]["options"]`. Add your
new field there as a sibling of the existing keys.

**Field schema reference:**

| Scenario | Schema snippet |
|---|---|
| Free string, optional | `{"type": "str", "required": False, "default": None}` |
| Integer, optional | `{"type": "int", "required": False, "default": None}` |
| Boolean | `{"type": "bool", "required": False, "default": False}` |

`required: True` is reserved for `vlan_id` only. Every new field must have a
sensible default so existing playbooks keep working unchanged.

---

## Step-by-step: adding a new field

The example below adds a fictional SVI `mtu` field that maps to:

```
interface vlan <id>
mtu 9000
exit
```

### Step 1 — add to `build_vlan_commands` in `vlan_builder.py`

Read the value near the other optional keys, and append it inside the SVI block,
after the IP command and before the SVI `exit`:

```python
mtu = vlan.get("mtu")
```

```python
    if ip_address or ip_dhcp:
        cmds.append(f"interface vlan {vlan_id}")

        if ip_address:
            cmds.append(f"ip address {ip_address} {subnet_mask}")
        elif ip_dhcp:
            cmds.append("ip address-alloc dhcp")

        if mtu is not None:
            cmds.append(f"mtu {mtu}")

        cmds.append("exit")
```

Update the builder docstring's `Optional keys` line:

```python
#            Optional keys: ``name``, ``ip_address``, ``subnet_mask``,
#                           ``ip_dhcp``, ``mtu``.
```

If the new field only makes sense with an SVI, validate that combination and
raise `ValueError` with a clear message.

### Step 2 — add to `argument_spec` in `jetstream_vlans.py`

Inside `argument_spec["vlans"]["options"]`, after `ip_dhcp`:

```python
"mtu": {
    "type": "int",
    "required": False,
    "default": None,
},
```

### Step 3 — smoke-test locally

Run this without a real switch:

```python
import sys
sys.path.insert(0, ".")
from plugins.module_utils.vlans.vlan_builder import build_vlan_commands

cmds = build_vlan_commands({
    "vlan_id": 10,
    "name": "Servers",
    "ip_address": "192.168.10.1",
    "subnet_mask": "255.255.255.0",
    "ip_dhcp": False,
    "mtu": 9000,               # ← your new field
})
assert "mtu 9000" in cmds, cmds
assert cmds[-1] == "exit", cmds

bare = build_vlan_commands({"vlan_id": 20, "mtu": 9000})
assert "mtu 9000" not in bare, bare

print("OK")
```

### Step 4 — update unit tests

Add the new field to `tests/unit/test_jetstream_vlans.py` for both:

- a case where the field is set and emits the command,
- a case where the field is `None` and emits nothing.

### Step 5 — verify the module parses cleanly

```bash
python3 -c "import ast, pathlib; ast.parse(pathlib.Path('plugins/modules/jetstream_vlans.py').read_text()); print('OK')"
python3 -m pytest tests/unit/test_jetstream_vlans.py -q
```

---

## Current fields reference

| YAML field | Python key | Type | Default | CLI command emitted |
|---|---|---|---|---|
| `vlan_id` | `vlan_id` | int | — required | `vlan <id>` |
| `name` | `name` | str | `None` | `name <name>` inside VLAN context |
| `ip_address` | `ip_address` | str | `None` | `ip address <ip> <mask>` inside SVI context |
| `subnet_mask` | `subnet_mask` | str | `None` | part of `ip address`; required with `ip_address` |
| `ip_dhcp` | `ip_dhcp` | bool | `False` | `ip address-alloc dhcp` inside SVI context |

`ip_address` and `ip_dhcp` are mutually exclusive.

---

## Config mode verification

Both `configure_vlan()` and `configure_interface()` call
`ensure_global_config(net_connect)` before sending their block. After a
context-entering command they call `require_config_mode(...)`:

```python
if cmd.startswith("interface vlan "):
    require_config_mode(net_connect, "interface", context=f"VLAN {vlan_id}")
elif cmd.startswith("vlan "):
    require_config_mode(net_connect, "vlan", context=f"VLAN {vlan_id}")
```

`config_mode.py` recognises:

```
(config)#           -> global
(config-vlan)#      -> vlan
(config-if)#        -> interface
(config-if-range)#  -> interface-range
```

If the switch did not enter the expected context, the module raises a clear
`RuntimeError` instead of sending the next command at the wrong level.

---

## What `send_command` does

```
plugins/module_utils/send_command.py
```

Wraps `net_connect.send_command()` with:

- `delay_factor=2.0`, `read_timeout=30` — safe for slow switches
- **No retry on empty output.** An empty result is normal for silent config
  commands such as `vlan 10` and `interface vlan 10`; resending would repeat the
  command in the new context and produce `Error: Bad command`.
- Opt-in timeout retries via `retries=` and `read_timeout=`.
- Optional `mode_aware=True`: after a `ReadTimeout`, the prompt is compared with
  the prompt captured before the command. Same prompt → retry; changed prompt →
  assume the command was applied and do not resend.

`configure_vlan()` uses:

```python
send_command(
    net_connect,
    cmd,
    expect_string=_CONFIG_PROMPT,
    retries=1,
    mode_aware=True,
)
```

The builder never calls this. The module sends each returned command.

---

## Check mode

`configure_vlan()` receives `check_mode: bool`. When `True`, it records the
command list with `changed: False` and returns without connecting changes to the
switch. The builder still runs so the preview matches the commands that would
run.

---

## Live test

```
tests/live_tests/vlans.py
```

Exercises four cases against a real switch:

1. named VLAN with a static SVI,
2. named VLAN without an SVI,
3. DHCP SVI without a name,
4. bare VLAN.

Run it from `tests/live_tests/`:

```bash
cd tests/live_tests
python3 vlans.py --check   # report only
python3 vlans.py           # push configuration
```

Do not use a management VLAN or management subnet for the static SVI case.

---

## Invariants — never break these

- `build_vlan_commands` has no side effects. Same input → same output.
- A field at its default value must not emit a CLI command.
- Every entered context block (`vlan <id>`, `interface vlan <id>`) is closed with
  `exit`.
- `exit` is the final command of each context block.
- No field in `argument_spec` may be `required: True` except `vlan_id`.
- `build_vlan_commands` must be importable with plain Python (no Ansible, no
  Netmiko).
- `ip_address` and `ip_dhcp` stay mutually exclusive.

---

## Things not implemented (known limits)

- **No idempotency.** The module always pushes commands. There is no `show vlan`
  read before writing.
- **No `state: absent`.** Deleting a VLAN or removing an SVI IP requires
  `no vlan <id>` / `no ip address` — not implemented.
- **No SVI `no shutdown`.** SVIs on JetStream come up automatically when the VLAN
  exists. Add an `svi_enabled` bool field if a firmware requires it.
- **`subnet_mask` is dotted-decimal only.** CIDR prefix notation is not handled.
