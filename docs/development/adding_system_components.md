# Adding Components to `jetstream_system`

This document is written for a future AI agent or developer picking up this
module cold. Read it fully before touching any file.

---

## Repository layout (relevant paths)

```
plugins/
  modules/
    jetstream_system.py           # Ansible module entry point
  module_utils/
    send_command.py               # sends one CLI command over Netmiko
    collector.py                  # ResultCollector: accumulates per-step results
```

Unlike `jetstream_interfaces`, this module has **no separate pure command
builder**. Each helper function builds its CLI string inline and calls
`send_command()` itself. A new system setting touches exactly **one file**:

1. `jetstream_system.py` — the `argument_spec` in `main()` (what YAML the user
   may write) **and** the helper function that emits the CLI command.

`main()` is the only place that should call `module.exit_json()` /
`module.fail_json()`. Helpers record results with `collector.add_step()` and
return.

---

## How `run_module()` executes

The module connects, enables, enters config mode, then runs helpers in order:

1. `set_general_information` — hostname, location, contact
2. `configure_dns` — primary / secondary DNS
3. `configure_ntp` — NTP (applied only when `type == "ntp"` and `ntp_utc`,
   2+ servers, and `ntp_fetch_time` are all provided)

`set_general_information` is the only helper that reads current state first
(`show system-info`) and skips a field when it already matches — the closest
thing to idempotency in this module. The other helpers push whenever the value
is truthy.

---

## Commands emitted

| Section | YAML field | CLI command |
|---|---|---|
| `system` | `hostname` | `hostname <v>` |
| `system` | `location` | `location <v>` |
| `system` | `contact` | `contact-info <v>` |
| `dns` | `primary` | `ip dns-address primary <v>` |
| `dns` | `secondary` | ` ip dns-address primary <v> secondary <v>` |
| `ntp` | all | `system-time ntp <utc> <s1> <s2> [<fetch>] [<s3> <s4> <s5>]` |

---

## Argument spec

`system` lives under `argument_spec["system"]["options"]`:

| YAML field | Type | Default | CLI command emitted |
|---|---|---|---|
| `hostname` | str | `None` | `hostname <v>` (skipped when already equal) |
| `location` | str | `None` | `location <v>` |
| `contact` | str | `None` | `contact-info <v>` |

`dns` lives under `argument_spec["dns"]["options"]`:

| YAML field | Type | Default | CLI command emitted |
|---|---|---|---|
| `primary` | str | `None` | `ip dns-address primary <v>` |
| `secondary` | str | `None` | `secondary <v>` appended when present |

`ntp` lives under `argument_spec["ntp"]["options"]`:

| YAML field | Type | Default | CLI command emitted |
|---|---|---|---|
| `type` | str | `None` | must be `"ntp"` to apply |
| `ntp_utc` | str | `None` | UTC offset in `system-time ntp` |
| `ntp_servers` | list[str] | `[]` | servers in `system-time ntp` |
| `ntp_fetch_time` | int | `None` | fetch interval appended |

---

## Field schema reference

| Scenario | Schema snippet |
|---|---|
| Free string, optional | `{"type": "str", "required": False, "default": None}` |
| String with fixed options | `{"type": "str", "required": False, "default": "all", "choices": ["all", "tagged"]}` |
| Integer, optional | `{"type": "int", "required": False, "default": None}` |
| List of strings | `{"type": "list", "elements": "str", "required": False, "default": []}` |
| Boolean | `{"type": "bool", "required": False, "default": False}` |

No field may become `required: True` — every field must have a sensible default
so existing playbooks keep working.

> **Deviation — booleans with omission detection.** When a boolean field must
> distinguish "not specified" from "explicitly false", use `default: None`
> instead of `default: False`. `lldp.enabled` follows this pattern: `None`
> means the user omitted it (skip), `False` means explicitly disable. The
> `default: False` convention above applies to booleans without this
> requirement.

---

## Step-by-step: adding a fictional system field `domain_name`

This example adds `domain_name` under `system`, emitting:

```
ip domain-name corp.example
```

### Step 1 — add to `argument_spec` in `jetstream_system.py`

Inside `argument_spec["system"]["options"]`:

```python
"domain_name": {"type": "str", "required": False, "default": None},
```

### Step 2 — wire it into `set_general_information`

Add it to the `params_to_commands` map; the existing loop handles
skip-when-empty, check mode, and the collector step:

```python
params_to_commands: dict[str, str] = {
    "hostname": "hostname",
    "location": "location",
    "contact": "contact-info",
    "domain_name": "ip domain-name",
}
```

That is all — no `send_command` or check-mode changes needed.

### Step 3 — smoke-test locally without a switch

In check mode `read_system_info()` is not called, so a `None` connection is
fine:

```python
from plugins.module_utils.collector import ResultCollector
from plugins.modules.jetstream_system import set_general_information

collector = ResultCollector()
collector.set_basic_info(switch="192.0.2.10", check_mode=True, verbosity=0)
set_general_information(
    None, {"domain_name": "corp.example"}, collector, check_mode=True
)
step = collector._steps[-1]
assert "ip domain-name corp.example" in step["commands_sent"]
assert step["changed"] is True
print(step["commands_sent"])
# ['ip domain-name corp.example']
```

Repeat with `domain_name=None` and confirm no command is emitted.

### Step 4 — verify the module parses cleanly

```bash
python3 -c "import ast, pathlib; ast.parse(pathlib.Path('plugins/modules/jetstream_system.py').read_text()); print('OK')"
```

---

## Invariants — never break these

- `main()` performs the final `module.exit_json()` / `module.fail_json()`.
  Helpers record results with `collector.add_step()` and return; do not add
  new exit points in helpers.
- A field at its default value must not emit a CLI command.
- In check mode, never call `send_command`; record `changed: False` and the
  planned command instead.
- No new `required: True` fields — every field must have a sensible default.

---

## What `send_command` does

```
plugins/module_utils/send_command.py
```

Wraps `net_connect.send_command()` with:
- `delay_factor=2.0`, `read_timeout=30` — safe for slow switches
- Up to 3 retries on empty output (JetStream quirk)
- Returns stripped output string

Helpers call this directly; there is no separate builder to route through.

---

## What `ResultCollector` does

```
plugins/module_utils/collector.py
```

Accumulates results across every helper call.
`collector.add_step(name, step_result)` records one step. The `steps` result is
available at every verbosity level (trimmed to `step`, `name`, `changed`,
`msg`, `settings` below verbosity 3). At verbosity 2 or higher, `system_info`
and `dns_info` appear. The top-level `commands_sent` field appears only at
verbosity 4 or higher and contains commands actually sent. Check mode records
planned commands in `steps` but not in `commands_sent`.

---

## Check mode

Every helper receives `check_mode` (via `module.check_mode`). When `True`, it
records the command with `changed: False` and returns without calling
`send_command`. `set_general_information` also skips the `show system-info`
read in check mode.

---

## Things not implemented (known limits)

- **NTP docs/code mismatch.** `ntp` is documented as "accepted but not applied
  yet", yet `configure_ntp()` applies it when `type == "ntp"` and `ntp_utc` +
  2+ servers + `ntp_fetch_time` are all set.
- **No read-before-write for DNS.** `configure_dns()` always pushes when
  `primary` is given; only `set_general_information` reads current state first.
- **No `state` param** — the module always applies the desired config.
