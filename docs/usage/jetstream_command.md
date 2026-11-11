# Using `jetstream_command`

`lachlanstone.jetstream.jetstream_command` connects to a TP-Link JetStream (Omada) switch over SSH and runs one or more CLI commands. For each command it returns the raw output, the output split into lines, a simple key/value parse, and a TextFSM parse when a template matches.

The module never changes its own `changed` state: it always reports `changed: false`. It does not know whether a command you send alters the switch.

## Quick start

```yaml
- name: Show system information and VLANs
  lachlanstone.jetstream.jetstream_command:
    host: 192.0.2.10
    username: admin
    password: "{{ vault_switch_password }}"
    enable_password: "{{ vault_switch_enable_password }}"
    command_level: enable
    commands:
      - show system-info
      - show vlan
  register: switch_result
```

## Connection options

| Option | Default | Notes |
|---|---|---|
| `host` | required | Switch hostname or IP. |
| `port` | `22` | SSH port. |
| `username` | required | SSH user. |
| `password` | `""` | SSH password. |
| `enable_password` | `""` | Privileged-mode password. |
| `read_timeout` | `30` | Seconds to wait for the prompt. Falls back to `JETSTREAM_READ_TIMEOUT`. Must be positive. |

## Command options

| Option | Type | Effect |
|---|---|---|
| `command_level` | `cli` / `enable` / `config` | CLI mode the commands run in. Default `cli`. |
| `commands` | list[str] | Commands to run, in order. |
| `command` | str | A single command. Ignored when `commands` is set. |

If neither `command` nor `commands` is given, `show system-info` runs.

### Command level

| Value | Mode |
|---|---|
| `cli` | User mode. Nothing is entered. |
| `enable` | Enters privileged mode (uses `enable_password`). |
| `config` | Enters privileged mode, then global configuration mode. |

The mode is entered once, before the first command, and all commands run in it.

## What happens on each run

1. Connect over SSH (Netmiko device type `tplink_jetstream`).
2. Enter privileged and/or config mode according to `command_level`.
3. For each command, in order, run it twice: once asking Netmiko to apply TextFSM, once for the plain output. The command therefore reaches the switch two times.
4. Build one result entry per command.

Any exception (connection failure, bad credentials, read timeout, invalid `read_timeout`) fails the task with the exception text as `msg`. Results gathered so far are not returned.

## TextFSM parsing

`textfsm_parsed` is filled by Netmiko's TextFSM support. Netmiko finds templates through the `NET_TEXTFSM` environment variable. This collection ships a template in `extras/ntc_templates/`:

| Command | Template |
|---|---|
| `show system-info` | `tplink_jetstream_show_system-info.textfsm` |

Point `NET_TEXTFSM` at the `extras/ntc_templates` directory of the installed collection (the one containing `index` and `templates/`). Set it in the environment of the process that runs the module, for example:

```bash
export NET_TEXTFSM=~/.ansible/collections/ansible_collections/lachlanstone/jetstream/extras/ntc_templates
```

The `show system-info` template extracts: `SYSTEM_DESCRIPTION`, `SYSTEM_NAME`, `SYSTEM_LOCATION`, `CONTACT_INFORMATION`, `HARDWARE_VERSION`, `SOFTWARE_VERSION`, `BOOTLOADER_VERSION`, `MAC_ADDRESS`, `SERIAL_NUMBER`, `SYSTEM_TIME`, `RUNNING_TIME`.

When no template matches (or `NET_TEXTFSM` is not set), `textfsm_parsed` holds the raw output string instead of a list.

## Check mode

Not supported. In check mode the module exits with `changed: false` and `msg: "Check mode - no commands executed"`, without connecting to the switch. No `commands` key is returned.

## Return values

| Key | When | Contents |
|---|---|---|
| `changed` | always | Always `false`. |
| `commands` | success | One entry per command, in the order run. |

Each `commands` entry:

| Key | When | Contents |
|---|---|---|
| `command` | always | The command that was run. |
| `stdout` | always | Raw output. |
| `stdout_lines` | always | Output lines with surrounding whitespace stripped and empty lines removed. |
| `textfsm_parsed` | always | TextFSM result (list of dicts), or the raw output string when no template matched. |
| `parsed` | at least one line matched | Dict built from lines containing ` - `: split at the first occurrence, key and value stripped. Later duplicate keys overwrite earlier ones. |

Output is the same at every verbosity level.

### Using the results

```yaml
- name: Show the software version
  ansible.builtin.debug:
    msg: "{{ switch_result.commands[0].parsed['Software Version'] }}"

# With NET_TEXTFSM set:
- name: Show the TextFSM version field
  ansible.builtin.debug:
    msg: "{{ switch_result.commands[0].textfsm_parsed[0].SOFTWARE_VERSION }}"
```

## Errors

| Message | Cause |
|---|---|
| `read_timeout must be a positive number of seconds, got ...` | `read_timeout` is zero or negative. |
| `JETSTREAM_READ_TIMEOUT must be a positive number of seconds, got ...` | The environment variable is not a positive number. |
| Other text | Netmiko/SSH exception (authentication, connection, timeout), passed through unchanged. |

## Limitations

- **Always `changed: false`.** Use `jetstream_save` and the dedicated modules for managed changes; this module is for running commands and reading output.
- **No check mode.** Nothing runs under `--check`.
- **Each command is sent twice.** Avoid commands that are not safe to repeat, especially with `command_level: config`.
- **`parsed` is a simple heuristic.** It only recognises ` - ` separated lines and will pick up any such line, including table rows.
- **One bundled template.** Only `show system-info` has a TextFSM template.
