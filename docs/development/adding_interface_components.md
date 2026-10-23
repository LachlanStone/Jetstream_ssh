# Adding Components to `jetstream_interfaces`

This document is written for a future AI agent or developer picking up this module cold.
Read it fully before touching any file.

---

## Repository layout (relevant paths)

```
plugins/
  modules/
    jetstream_interfaces.py              # Ansible module entry point
  module_utils/
    interfaces/
      __init__.py                        # empty, marks package
      interface_builder.py              # pure command builder — no Ansible, no Netmiko
    send_command.py                      # sends one CLI command over Netmiko
    config_mode.py                       # prompt-based CLI mode detection/guards
    collector.py                         # ResultCollector: accumulates per-step results
```

Every new interface parameter touches exactly **two files**:
1. `interface_builder.py` — what CLI commands to emit
2. `jetstream_interfaces.py` — what YAML the user is allowed to write

Nothing else. `configure_interface()` in the module calls `build_commands()` and
iterates the result — you do not touch that function for a new field.

---

## The two-file contract

### `interface_builder.py` — `build_commands(iface)`

`iface` is a plain dict (one element from `module.params["interfaces"]`).
The function returns a flat `list[str]` of CLI commands in the order the switch
expects them, bracketed by `interface <port-type> X/Y/Z` at the top and
`exit` at the bottom.

**Rules for adding a command here:**

- Read the value with `.get("your_field")`.
- Skip the command entirely when the value is falsy / equals the switch default.
  This keeps the module idempotent-friendly (no unnecessary config churn).
- Append the command string to `cmds` in the correct CLI order.
  CLI order for this switch: `enabled` (`shutdown` / `no shutdown`) → `speed` → `pvid` → `allowed vlan` → feature flags → `description` → `exit`.
- Raise `ValueError` only for invalid values that cannot be caught by `choices`
  in the argument spec (e.g. a bad combination of fields).
- No Ansible imports. No Netmiko imports. The function must be importable and
  testable with plain Python.

### `jetstream_interfaces.py` — `main()` → `argument_spec`

The `interfaces` list element lives under `argument_spec["interfaces"]["options"]`.
Add your new field there as a sibling of the existing keys.

**Field schema reference:**

| Scenario | Schema snippet |
|---|---|
| Free string, optional | `{"type": "str", "required": False, "default": None}` |
| String with fixed options | `{"type": "str", "required": False, "default": "all", "choices": ["all", "tagged"]}` |
| Integer, optional | `{"type": "int", "required": False, "default": None}` |
| List of integers | `{"type": "list", "elements": "int", "required": False, "default": []}` |
| Boolean | `{"type": "bool", "required": False, "default": False}` |

`required: True` is reserved for `name` only. Every new field must have
a sensible default so existing playbooks keep working without changes.

---

## Step-by-step: adding a new field

The example below adds a fictional `storm_control` field that maps to:
```
switchport general storm-control broadcast 10
```

### Step 1 — add to `build_commands` in `interface_builder.py`

Locate the block where the existing feature flags live (after the VLAN lines,
before `description`). Add:

```python
storm_control = iface.get("storm_control")
if storm_control is not None:
    cmds.append(f"switchport general storm-control broadcast {storm_control}")
```

Also update the `Optional keys` line in the docstring:

```python
#            Optional keys: ``port_type``, ``speed``, ``enabled``,
#                           ``description``, ``pvid``, ``vlans_untagged``,
#                           ``vlans_tagged``, ``acceptable_frame_type``,
#                           ``storm_control``.
```

### Step 2 — add to `argument_spec` in `jetstream_interfaces.py`

Inside `argument_spec["interfaces"]["options"]`, after `acceptable_frame_type`:

```python
"storm_control": {
    "type": "int",
    "required": False,
    "default": None,
},
```

### Step 3 — smoke-test locally

Run this without a real switch:

```python
import sys
sys.path.insert(0, "/path/to/ansible_collections/lachlanstone/jetstream")
from plugins.module_utils.interfaces.interface_builder import build_commands

cmds = build_commands({
    "name": "1/0/1",
    "port_type": "gigabitEthernet",
    "speed": None,
    "enabled": None,
    "pvid": None,
    "description": None,
    "vlans_untagged": [],
    "vlans_tagged": [],
    "acceptable_frame_type": "all",
    "storm_control": 10,       # ← your new field
})
print("\n".join(cmds))
```

Expected output includes `switchport general storm-control broadcast 10` before `exit`.
Also run the same with `storm_control=None` and confirm the line is absent.

### Step 4 — verify the module parses cleanly

```bash
python3 -c "import ast, pathlib; ast.parse(pathlib.Path('plugins/modules/jetstream_interfaces.py').read_text()); print('OK')"
```

---

## Current fields reference

| YAML field | Python key | Type | Default | CLI command emitted |
|---|---|---|---|---|
| `name` | `name` | str | — required | port ID portion of `interface <port-type> X/Y/Z` |
| `port_type` | `port_type` | str | `"gigabitEthernet"` | interface prefix: `gigabitEthernet` / `two-gigabitEthernet` / `ten-gigabitEthernet` / `fastEthernet` |
| `speed` | `speed` | str | `None` (omitted) | `speed <value>` — choices: `10`, `100`, `1000`, `2500`, `10000`, `auto` |
| `enabled` | `enabled` | bool | `None` (omitted) | `no shutdown` when `True`, `shutdown` when `False`, nothing when omitted |
| `pvid` | `pvid` | int | `None` (omitted) | `switchport pvid <N>` |
| `vlans_untagged` | `vlans_untagged` | list[int] | `[]` | `switchport general allowed vlan <N,...> untagged` |
| `vlans_tagged` | `vlans_tagged` | list[int] | `[]` | `switchport general allowed vlan <N,...> tagged` |
| `acceptable_frame_type` | `acceptable_frame_type` | str | `"all"` | `switchport general acceptable-frame-type tagged-only` (skipped when `"all"`) |
| `description` | `description` | str | `None` | `description <text>` (quoted if contains spaces) |

### `port_type` vs `speed` — important distinction

`port_type` selects **which physical port family** the CLI addresses — it must match the hardware, not the negotiated speed. A 10G SFP+ port is always `ten-gigabitEthernet` even when forced to run at 1G. `speed` then sets what speed that port negotiates on the wire.

```
# SFP+ port 25 running at 1G (from TP-Link official docs):
interface ten-gigabitEthernet 1/0/25
speed 1000
```

Omitting `port_type` defaults to `gigabitEthernet`, correct for the vast majority of ports. Set it explicitly only for 2.5G, 10G, or 100M ports.

> **Alias note:** `_PORT_TYPE_CLI` in the builder also accepts short aliases
> (`gi`, `tw`, `te`, `fa`). These are intentionally **not** listed in the
> `argument_spec` choices — Ansible validates the YAML value and the builder
> resolves it. Do not add aliases to `choices`; add them only to `_PORT_TYPE_CLI`
> if the switch CLI gains new shorthand.

---

## Invariants — never break these

- `build_commands` has no side effects. Same input → same output, always.
- A field set to its default value must not emit a CLI command.
  The switch is already in that state; pushing it again wastes a round-trip and
  makes diffs noisy.
- `exit` is always the last command in the returned list. The switch context
  must be back at global config before the next interface block starts.
- `description` is always the last substantive command, before `exit`.
  Some JetStream firmware versions reject `description` mid-block.
- `configure_interface()` must call `ensure_global_config()` before each block
  and `require_config_mode(net_connect, "interface", ...)` after the
  `interface ...` command. If the switch did not enter interface mode, raise
  instead of sending the remaining commands at global config.
- No field in `argument_spec` may be `required: True` except `name`.
  Adding a required field breaks every existing playbook silently at runtime.

---

## What `send_command` does

```
plugins/module_utils/send_command.py
```

Wraps `net_connect.send_command()` with:

- `delay_factor=2.0`, `read_timeout=30` — safe for slow switches
- **No retry on empty output.** Empty output is normal for silent config
  commands such as `interface gigabitEthernet 1/0/1`; resending repeats the
  command inside the new context and produces `Error: Bad command`.
- Opt-in timeout retries via `retries=` and `read_timeout=`.
- Optional `mode_aware=True`: after a `ReadTimeout`, the prompt is compared with
  the prompt captured before the command. Same prompt → retry; changed prompt →
  assume the command was applied and do not resend.

`configure_interface()` uses `retries=1, mode_aware=True`.

You do not call this from the builder. `configure_interface()` in the module
calls it once per command returned by `build_commands()`.

---

## What `ResultCollector` does

```
plugins/module_utils/collector.py
```

Accumulates results across every `configure_interface()` call.
`collector.add_step(name, step_result)` records one step. The `steps` result is
available at every verbosity level with each step's name, status, and message.
Interface steps also include configured `settings`. At verbosity 3 or higher,
steps include command previews and device output. The top-level `commands_sent`
field appears only at verbosity 4 or higher and contains commands actually sent.
Check mode records planned commands in `steps` but not in `commands_sent`.


---

## Check mode

`configure_interface()` in the module receives `check_mode: bool`.
When `True`, it records the command list with `changed: False` and returns
without calling `send_command`. Step summaries appear at every verbosity level;
the command preview appears only at verbosity 3 or higher. The builder still
runs in check mode so the preview matches the commands that would run.

---

## Things not implemented (known limits)

- **No idempotency.** The module always pushes commands. There is no `show interface` read before writing. To add it: write a TextFSM template under `ntc_templates/templates/`, parse current state, diff against desired, skip commands that are already correct.
- **No `state: absent`.** Removing a VLAN from a port or reverting a field to default requires knowing the `no` form of each command. Add a `state` param (`present` / `absent`) and a second command-list builder (`build_absent_commands`) if needed.
