# Using `jetstream_user`

`lachlanstone.jetstream.jetstream_user` manages local user accounts on TP-Link JetStream (Omada) switches: create, update privilege or password, and remove. Accounts can be given as a single user or as a batch, and the running config can optionally be saved afterwards.

## Quick start

```yaml
- name: Create an admin and remove an old account
  lachlanstone.jetstream.jetstream_user:
    host: 192.0.2.10
    username: admin
    password: "{{ vault_switch_password }}"
    enable_password: "{{ vault_switch_enable_password }}"
    users:
      - name: netops
        privilege: admin
        password: "{{ vault_netops_password }}"
      - name: old_admin
        state: absent
    save_config: true
```

Single user:

```yaml
- name: Create a guest user
  lachlanstone.jetstream.jetstream_user:
    host: 192.0.2.10
    username: admin
    password: "{{ vault_switch_password }}"
    enable_password: "{{ vault_switch_enable_password }}"
    name: guest_audit
    privilege: guest
    password_type: password
    user_password: "{{ vault_guest_password }}"
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

## User options

Use `name` (with the options below) for one account, `users` for a list, or both. If both are given, the single user is processed first, then the list in order. If neither is given, the module returns `changed: false` with `No user accounts specified to configure.` and never connects to the switch.

| Option | Default | Effect |
|---|---|---|
| `name` | none | Account name. Max 16 characters, no spaces. |
| `privilege` | `admin` | `admin`, `guest`, `operator`, `power_user` or `user`. Older models mainly support `admin` and `guest`; newer ones `admin`, `operator`, `power_user` and `user`. |
| `password_type` | `secret` | `secret` (MD5 secret, recommended) or `password`. |
| `encryption_type` | `0` | Format of the string you supply: `0` plaintext (the switch encrypts it), `5` an already-encrypted MD5 secret, `7` an already-encrypted password. |
| `user_password` | none | The account's password or secret string. |
| `state` | `present` | `present` or `absent`. |
| `update_password` | `always` | `always` or `on_create`. See below. |
| `save_config` | `false` | Save to startup config after changes. Top-level only. |
| `users` | none | List of accounts. |

Each `users` item accepts `name` (required), `privilege`, `password_type`, `encryption_type`, `password`, `state` and `update_password`, with the same values and defaults. Note the password key is `password` inside `users` but `user_password` at top level (top-level `password` is the SSH password). Options are per item and are not inherited from the top level.

Accounts with lower privilege (`operator`, `power_user`, `user`) may need the switch's enable password configured to run privileged commands.

## States

- **`present`**: creates the account, or updates an existing one, by sending `user name <name> privilege <privilege> <password_type> <encryption_type> <password>`. A new account requires a password.
- **`absent`**: sends `no user name <name>`. If the account isn't on the switch, nothing is sent for it.

### `update_password`

Applies to `state: present`.

| Situation | `always` | `on_create` |
|---|---|---|
| Account doesn't exist | Created. Password required. | Created. Password required. |
| Account exists, same privilege | Command sent every run (password required). | Skipped. |
| Account exists, different privilege | Command sent (password required). | Command sent. Without a password only the privilege is changed (`user name <name> privilege <privilege>`); with a password it is sent too. |

The module can't read passwords back, so with `always` it cannot tell whether a password already matches. Every run with an existing account reports `changed: true`. Use `on_create` for idempotent runs.

## What happens on each run

1. The module reads existing accounts with `show user configuration`, falling back to `show user account-list`.
2. Each entry is handled in order; names longer than 16 characters or containing spaces fail the task.
3. Commands are sent in config mode. Nothing is read back or verified afterwards.
4. If `save_config` is true, something changed and not in check mode, `copy running-config startup-config` is sent.

## Passwords and `no_log`

- `password`, `enable_password`, `user_password` and `users[].password` are marked `no_log`, so Ansible masks them in output.
- The returned `cmd` and every step's `command`/`commands` show the command with the password replaced by `<redacted>`.
- With `encryption_type: 5` or `7` the hash is what is redacted; it is still sent to the switch as given.

## Check mode

`--check` reads the switch and plans, but sends nothing. Steps for the would-be changes are still recorded, so `changed` is `true` when changes would be made and `false` when nothing would be. `cmd` stays empty and `commands_sent` is empty. `save_config` is not executed in check mode.

## Return values

| Key | When | Contents |
|---|---|---|
| `changed` | always | `true` if any create, update or removal was sent (or planned, in check mode). |
| `msg` | always | Message of the last step, e.g. `Created user 'netops' with privilege 'admin'`, `Updated user ...`, `Removed user ...`. Empty if no steps ran. |
| `switch` | always | The `host` connected to. |
| `check_mode` | always | Whether the run was in check mode. |
| `current_state` | always | Name of the last step recorded. |
| `cmd` | always | Last command sent, password redacted. Empty in check mode. |
| `steps` | always | One step per account: `configure_user` or `remove_user`, plus `save_config` if run. Each has `step`, `name`, `changed`, `msg`. |
| `commands_sent` | `-vvvv` | Every command sent, redacted. |

At `-vvv` and up each step also includes `command` and `commands`.

## Errors

| Message | Cause |
|---|---|
| `Invalid username '<name>': maximum 16 characters and no spaces allowed.` | Name too long or contains a space. |
| `Password is required to create new user '<name>'.` | New account with no password. |
| `Password must be specified when updating user '<name>' on JetStream switch CLI.` | Existing account, `update_password: always` and no password. |

Connection and command failures from Netmiko are reported as the task's failure message.

## Limitations

- **Passwords can't be compared.** `update_password: always` is never idempotent.
- **Existing accounts come from CLI parsing.** If neither `show user configuration` nor `show user account-list` yields users, every account is treated as nonexistent, so `absent` entries are skipped and `present` entries are created.
- **Privilege only.** Only privilege is compared for existing users; status is parsed but not managed.
- **Saving only on change.** `save_config` runs only when something changed.
