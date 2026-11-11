# Using `jetstream_system`

`lachlanstone.jetstream.jetstream_system` sets general system settings on TP-Link JetStream (Omada) switches: hostname, location, contact, DNS servers, NTP and global LLDP. Every block is optional; only the blocks you give are applied.

Idempotence differs by block:

- `system` (hostname, location, contact) reads the switch first and skips values that already match.
- `dns`, `ntp` and `lldp` do not read the switch. They send their command on every run and always report `changed: true`.

## Quick start

```yaml
- name: Set hostname, location, contact and DNS
  lachlanstone.jetstream.jetstream_system:
    host: 192.0.2.10
    username: admin
    password: "{{ vault_switch_password }}"
    enable_password: "{{ vault_switch_enable_password }}"
    system:
      hostname: switch-01
      location: Server Room
      contact: admin@example.com
    dns:
      primary: 192.0.2.53
      secondary: 198.51.100.53
```

## Connection options

| Option | Default | Notes |
|---|---|---|
| `host` | required | Switch hostname or IP. |
| `port` | `22` | SSH port. |
| `username` | required | SSH user. |
| `password` | `""` | SSH password. |
| `enable_password` | `""` | Privileged-mode password. |
| `read_timeout` | `30` | Seconds to wait for the prompt. Falls back to `JETSTREAM_READ_TIMEOUT`. |

## System options

### `system`

An option you leave out, or set to an empty string, is not managed.

| Option | Type | Command sent |
|---|---|---|
| `hostname` | str | `hostname <value>` |
| `location` | str | `location <value>` |
| `contact` | str | `contact-info <value>` |

Before sending, the module runs `show system-info` and compares. A value that already matches is skipped. If the output can't be read or parsed, the module applies every value you gave.

### `dns`

| Option | Type | Effect |
|---|---|---|
| `primary` | str | Primary DNS server. |
| `secondary` | str | Secondary DNS server. Requires `primary`. |

Sends `ip dns-address primary <primary>`, with ` secondary <secondary>` appended when given. `secondary` alone fails the task. To change only the secondary server, repeat `primary` as well.

### `ntp`

Applied only when `type: ntp`. Any other `type` is ignored silently, and so is omitting `type`.

| Option | Type | Effect |
|---|---|---|
| `type` | str | Must be `ntp` to apply. |
| `ntp_utc` | str | UTC offset, e.g. `"+00:00"` or `"+10:00"`. Required. |
| `ntp_servers` | list[str] | At least 2 servers, up to 5. Servers past the fifth are ignored. Required. |
| `ntp_fetch_time` | int | Polling interval in minutes. Required. |

Sends `system-time ntp <ntp_utc> <server1> <server2> <ntp_fetch_time> [<server3> ... <server5>]`.

### `lldp`

| Option | Type | Effect |
|---|---|---|
| `enabled` | bool | `true` sends `lldp run`, `false` sends `no lldp run`. Omit to leave LLDP alone. |

## What happens on each run

1. **Connect.** The module logs in over SSH and enters privileged then config mode.
2. **Apply, in this order:** `system`, `dns`, `ntp`, `lldp`. Each block records one step (`set_general_information`, `configure_dns`, `configure_ntp`, `configure_lldp`). `system` always records a step. The others record one only when you supplied them (and, for `ntp`, `type: ntp`).
3. **Report.** If any step failed, the task fails with that step's message. Commands from earlier blocks have already been sent by then and are not rolled back.

Nothing is read back after the change to confirm it.

## Check mode

`--check` connects but sends no configuration commands, and `commands_sent` stays empty.

- `system`: the switch is not read, so every value you gave is counted as a change. `changed` is `true`, even if the switch already matches.
- `dns`, `ntp`, `lldp`: the step reports `changed: false`. The command it would send is in the step's `commands` at `-vvv` and up.

## Return values

| Key | When | Contents |
|---|---|---|
| `changed` | always | `true` if any step changed something (see Check mode). |
| `msg` | always | Message of the last step recorded. |
| `switch` | always | Host the module connected to. |
| `current_state` | always | Name of the last step recorded. |
| `check_mode` | always | Whether the run was a check-mode run. |
| `cmd` | always | The last command sent. Empty in check mode. |
| `steps` | always | One entry per step, with `step`, `name`, `changed`, `msg`. |
| `system_info` | `-vv` and up | The `system` values you gave (`hostname`, `location`, `contact`; unset ones are `null`). This is the requested state, not what was read from the switch. |
| `commands` in each step | `-vvv` and up | Commands the step sent or, in check mode, would send. Steps also carry `command`, and `system_info` where present. |
| `commands_sent` | `-vvvv` | Every command actually sent, in order. |

`system_info` is returned only when `system` is given or already collected. The `system` step's `msg` is `Configured system info: hostname=..., location=..., contact=...` when something changed, and `No system info provided, nothing to configure` when nothing did, including when every value already matched.

### Using the results

```yaml
- name: Configure system
  lachlanstone.jetstream.jetstream_system:
    # ...
  register: result
  # run with -vvvv to see commands_sent

- name: Show last message
  ansible.builtin.debug:
    var: result.msg
```

## Errors

| Message | Cause |
|---|---|
| `DNS configuration requires 'primary' server when 'secondary' is specified.` | `dns.secondary` given without `dns.primary`. |
| `NTP configuration requires 'ntp_utc' (e.g., '+00:00').` | `type: ntp` without `ntp_utc`. |
| `NTP configuration on TP-Link JetStream CLI requires at least 2 servers in 'ntp_servers' (got N).` | Fewer than two NTP servers. |
| `NTP configuration requires 'ntp_fetch_time' (polling interval in minutes).` | `type: ntp` without `ntp_fetch_time`. |

Any connection or command exception also fails the task with the exception text.

## Limitations

- **`dns`, `ntp`, `lldp` are not idempotent.** They resend their command each run and report `changed: true`.
- **Check mode over-reports `system` changes.** The switch isn't read in check mode.
- **Values aren't validated.** Server addresses, UTC offsets and hostnames are sent as given. The switch decides whether they are valid.
- **Empty strings can't clear a setting.** An empty or omitted value is skipped.
- **Saving is separate.** Changes go to the running config. Use `jetstream_save` to persist them.
