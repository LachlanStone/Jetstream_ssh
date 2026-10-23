# Adding Components to `jetstream_acls`

This document is written for a future AI agent or developer picking up this
module cold. Read it fully before touching any file.

---

## Repository layout (relevant paths)

```
plugins/
  modules/
    jetstream_acls.py             # Ansible module entry point
  module_utils/
    acls/
      __init__.py                 # empty, marks package
      acl_classes.py              # ACL / ACLRule in-memory models — no Ansible, no Netmiko
      acls_parsers.py             # parse `show access-list` output + IP protocol name map
    send_command.py               # sends one CLI command over Netmiko
    collector.py                  # ResultCollector: accumulates per-step results
```

Unlike `jetstream_interfaces`, this module has **no separate pure command
builder**. Each helper function builds its CLI string inline and calls
`send_command()` itself. A new ACL field touches two places:

1. `jetstream_acls.py` — the `argument_spec` in `main()` (what YAML the user
   may write) **and** the helper function that emits the CLI command.
2. `plugins/module_utils/acls/acl_classes.py` — if the field lives on an ACL
   rule (`ACLRule`), since rules travel as dataclass instances, not plain dicts.

`main()` is the only place that should call `module.exit_json()` /
`module.fail_json()`. Helpers record results with `collector.add_step()` and
return.

---

## How `run_modules()` executes

The module connects, enters config mode, then runs helpers in this fixed order:

| Step | Helper | Command emitted | States that trigger it |
|---|---|---|---|
| 1 | `unbind_acl` | `no access-list bind <id>` | unbind, absent, update |
| 2 | `remove_acl` | `no access-list create <id>` | absent, update |
| 3 | `create_and_update_acl` | `access-list create <id> [name "..."]` | present, update |
| 4 | `create_and_update_acl_rules` | `access-list <rule_type> <id> rule <seq> <action> …` | present, update |
| 5 | `bind_acls` | `access-list bind <id>` | present, update |

`state: present` only unbinds/removes/creates when the switch state differs;
`state: update` always unbinds → removes → creates → binds. Each helper checks
`module.check_mode` and skips `send_command` when it is true.

---

## ACL argument spec

Top-level `acls` is a dict under `argument_spec["acls"]["options"]`:

| YAML field | Python key | Type | Default | CLI command emitted |
|---|---|---|---|---|
| `id` | `id` | str | required | `access-list create <id>` / `no access-list create <id>` / `access-list bind <id>` |
| `name` | `name` | str | `None` | `name "<name>"` appended to create |
| `vid` | `vid` | int | `None` | `vid <N>` on combined-type rules |
| `rule_type` | `rule_type` | str | `None` | `access-list ip\|combined … rule …` |
| `rules` | `rules` | list[dict] | `[]` | one `access-list … rule …` per rule |

ACL rule options live under `acls` → `rules` → `options`:

| YAML field | Python key | Type | Default | CLI command emitted |
|---|---|---|---|---|
| `seq` | `seq` | int | required | `rule <seq>` |
| `action` | `action` | str | `"permit"` | `permit` / `deny` |
| `logging` | `logging` | str | `"disable"` | `logging enable` / `logging disable` |
| `sip` | `sip` | str | `None` | `sip <ip> sip-mask <mask>` (with `sip_mask`) |
| `sip_mask` | `sip_mask` | str | `None` | `sip-mask <mask>` |
| `dip` | `dip` | str | `None` | `dip <ip> dip-mask <mask>` (with `dip_mask`) |
| `dip_mask` | `dip_mask` | str | `None` | `dip-mask <mask>` |
| `protocol` | `protocol` | int | `None` | `protocol <N>` — mutually exclusive with `protocol_name` |
| `protocol_name` | `protocol_name` | str | `None` | `protocol <N>` via `get_protocol_number()` — choices from `protocol_names()` |
| `dport` | `dport` | int | `None` | `d-port <p> d-port-mask <m>` — TCP (6) / UDP (17) only |
| `dport_mask` | `dport_mask` | int | `None` | `d-port-mask <m>` — defaults to `0000` when missing |

Rules flow through `ACLRule` in `acl_classes.py`; a new rule field must be
added to `ACLRule.__init__` / `ACLRule.from_dict` as well as to the argument
spec.

---

## Field schema reference

| Scenario | Schema snippet |
|---|---|
| Free string, optional | `{"type": "str", "required": False, "default": None}` |
| String with fixed options | `{"type": "str", "required": False, "default": "all", "choices": ["all", "tagged"]}` |
| Integer, optional | `{"type": "int", "required": False, "default": None}` |
| List of dicts | `{"type": "list", "elements": "dict", "required": False, "default": []}` |
| Boolean | `{"type": "bool", "required": False, "default": False}` |

No field may become `required: True` except the existing `id` (ACL) and `seq`
(rule). `mutually_exclusive=[["protocol", "protocol_name"]]` must remain.

---

## Step-by-step: adding a fictional rule field `remark`

This example adds a fictional `remark` to ACL rules that emits:

```
access-list combined 1001 rule 10 permit logging enable remark "print queue"
```

### Step 1 — extend the in-memory model in `acl_classes.py`

Add `remark` to `ACLRule.__init__`:

```python
def __init__(
    self,
    seq,
    action,
    logging=False,
    sip=None,
    sip_mask=None,
    dip=None,
    dip_mask=None,
    protocol_name=None,
    protocol=None,
    dport=None,
    dport_mask=None,
    remark=None,
):
    ...
    self.remark = remark
```

and to `ACLRule.from_dict`:

```python
remark=acl.get("remark"),
```

### Step 2 — add to `argument_spec` in `jetstream_acls.py`

Inside `argument_spec["acls"]["options"]["rules"]["options"]`:

```python
"remark": {
    "type": "str",
    "required": False,
    "default": None,
},
```

### Step 3 — wire the command in `create_and_update_acl_rules`

`rule` is an `ACLRule` instance here, so use attribute access:

```python
if rule.logging:
    cmd += " logging enable"
else:
    cmd += " logging disable"
if rule.remark:
    cmd += f' remark "{rule.remark}"'
```

### Step 4 — smoke-test locally without a switch

```python
from plugins.module_utils.acls.acl_classes import ACLRule

rule = ACLRule(seq=10, action="permit", logging=True, remark="print queue")
cmd = f"access-list combined 1001 rule {rule.seq} {rule.action}"
cmd += " logging enable" if rule.logging else " logging disable"
if rule.remark:
    cmd += f' remark "{rule.remark}"'
print(cmd)
# access-list combined 1001 rule 10 permit logging enable remark "print queue"
```

Repeat with `remark=None` and confirm nothing is appended.

### Step 5 — verify the module parses cleanly

```bash
python3 -c "import ast, pathlib; ast.parse(pathlib.Path('plugins/modules/jetstream_acls.py').read_text()); print('OK')"
```

---

## Invariants — never break these

- `main()` performs the final `module.exit_json()` / `module.fail_json()`.
  Helpers record results with `collector.add_step()` and return; do not add
  new exit points in helpers.
- A field at its default value must not emit a CLI command.
- In check mode, never call `send_command`; record `changed: False` and the
  planned command instead.
- ACL command order in a run is fixed: unbind → remove → create → rules → bind.
  Do not reorder the helper calls in `run_modules()`.
- Binding must include a target:
  `access-list bind <id> interface vlan <vid>`. A bare
  `access-list bind <id>` is rejected as an incomplete command.
- After unbinding for `state: update`, clear the stale `acl.is_bound` snapshot so
  the final bind step runs again.
- `mutually_exclusive=[["protocol", "protocol_name"]]` must remain in the
  argument spec.

---

## What `send_command` does

```
plugins/module_utils/send_command.py
```

Wraps `net_connect.send_command()` with:

- `delay_factor=2.0`, `read_timeout=30` — safe for slow switches
- **No retry on empty output.** Empty output is normal for silent config
  commands; resending repeats the command in the new context and produces
  `Error: Bad command`.
- Opt-in timeout retries: pass `retries=N` to retry only after a `ReadTimeout`.
- `mode_aware=True` compares prompts across a timeout. Same prompt → retry;
  changed prompt → assume the command was applied and do not resend.

The ACL module leaves timeout retries disabled for create/remove/rule/bind
commands because repeating them can create duplicates. The `show access-list`
and `show access-list bind` reads use `retries=1`.

Helpers call this directly; there is no separate builder to route through.

---

## What `ResultCollector` does

```
plugins/module_utils/collector.py
```

Accumulates results across every helper call.
`collector.add_step(name, step_result)` records one step. The `steps` result is
available at every verbosity level (trimmed to `step`, `name`, `changed`,
`msg`, `settings` below verbosity 3). At verbosity 3 or higher, steps include
full detail. At verbosity 2 or higher, `acl_info` appears. The top-level
`commands_sent` field appears only at verbosity 4 or higher and contains
commands actually sent. Check mode records planned commands in `steps` but not
in `commands_sent`.

---

## Check mode

Every helper receives `check_mode` (via `module.check_mode`). When `True`, it
records the command with `changed: False` and returns without calling
`send_command`.

---

## Things not implemented (known limits)

- **No per-rule diff.** `create_and_update_acl_rules` appends rules; it does
  not read existing rules and skip ones already correct, and never removes or
  updates individual rules despite the stale `TODO` comment.
  `get_current_acls()` only parses `seq`, `action`, and `logging`.
- **Fixed 5-second pause.** `time.sleep(5)` runs between rules — slow, but
  intentional for this hardware.
