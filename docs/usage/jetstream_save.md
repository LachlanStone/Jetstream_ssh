# Using `jetstream_save`

`lachlanstone.jetstream.jetstream_save` copies the running configuration of a TP-Link JetStream (Omada) switch to its startup configuration, so changes survive a reboot. The other modules only change the running config.

The module has no idempotence check: every real run sends the save command and reports `changed: true`.

## Quick start

```yaml
- name: Save running config to startup config
  lachlanstone.jetstream.jetstream_save:
    host: 192.0.2.10
    username: admin
    password: "{{ vault_switch_password }}"
    enable_password: "{{ vault_switch_enable_password }}"
```

Using the `write` command instead:

```yaml
- name: Save with write
  lachlanstone.jetstream.jetstream_save:
    host: 192.0.2.10
    username: admin
    password: "{{ vault_switch_password }}"
    enable_password: "{{ vault_switch_enable_password }}"
    command: write
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

## Module options

| Option | Type | Default | Effect |
|---|---|---|---|
| `command` | str | `copy running-config startup-config` | CLI command used to save. Choices: `copy running-config startup-config`, `write`. |

`copy running-config startup-config` is the standard command on JetStream and Omada switches. `write` is accepted only by certain firmware releases; use it if your switch supports it.

## What happens on each run

1. Connect over SSH and enter privileged mode (`enable`).
2. Send the chosen save command (through Netmiko's `save_config` when available).
3. Record one step, `save_config`, with the command and the switch output.

## Check mode

`--check` does not connect to the switch and sends nothing. `changed` is `false` and `check_mode` is `true`. The `save_config` step records the planned command in its `commands` list (visible at `-vvv` and up). Because nothing is sent, `cmd` is empty and `commands_sent` is empty. The step `msg` uses the same "Saved ..." wording as a real run.

Since no connection is made, check mode does not validate host, credentials or reachability.

## Return values

| Key | When | Contents |
|---|---|---|
| `changed` | always | `true` after a real run, `false` in check mode. |
| `msg` | always | `Saved running-config to startup-config using '<command>'`. |
| `switch` | always | The `host` value. |
| `check_mode` | always | Whether the run was in check mode. |
| `cmd` | always | The save command sent. Empty in check mode. |
| `current_state` | always | Name of the last step (`save_config`). |
| `steps` | always | One `save_config` step with `step`, `name`, `changed`, `msg`. |
| `commands_sent` | `-vvvv` | Commands sent. Empty in check mode. |

At `-vvv` and up, the step also includes `command`, `commands` and `stdout` (the switch output).

### Using the results

```yaml
- name: Save config
  lachlanstone.jetstream.jetstream_save:
    # ...
  register: result

- name: Show switch output
  ansible.builtin.debug:
    var: result.steps[0].stdout
```

Run with `-vvv` for `stdout` to be present.

## Errors

Any exception (SSH failure, authentication failure, read timeout, command error) fails the task with `msg` set to the exception text and `check_mode` in the result. The module adds no messages of its own. If a timeout occurs, raise `read_timeout`.

## Limitations

- **Always reports a change.** There is no comparison between running and startup config.
- **No verification.** The module does not check the switch output for success; it records `stdout` only.
- **Command choice is firmware dependent.** If `write` fails on your switch, use the default.
