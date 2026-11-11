# Using `jetstream_acls`

`lachlanstone.jetstream.jetstream_acls` manages one access list (ACL) and its rules on TP-Link JetStream (Omada) switches. It reads the ACLs defined and bound on the switch, then creates, binds, unbinds or removes the ACL named in `acls`, depending on `state`.

The module manages a single ACL per task. Run it once per ACL.

## Quick start

```yaml
- name: Create an ACL that permits printing traffic and bind it
  lachlanstone.jetstream.jetstream_acls:
    host: 192.0.2.10
    username: admin
    password: "{{ vault_switch_password }}"
    enable_password: "{{ vault_switch_enable_password }}"
    state: present
    acls:
      id: "1001"
      name: ALLOW_PRINT
      vid: 10
      rule_type: combined
      rules:
        - seq: 10
          action: permit
          sip: 10.0.0.0
          sip_mask: 255.255.0.0
          dip: 10.0.0.0
          dip_mask: 255.255.0.0
          protocol_name: TCP
          dport: 9100

- name: Remove an ACL
  lachlanstone.jetstream.jetstream_acls:
    host: 192.0.2.10
    username: admin
    password: "{{ vault_switch_password }}"
    enable_password: "{{ vault_switch_enable_password }}"
    state: absent
    acls:
      id: "1001"
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

## States

| `state` | What it does |
|---|---|
| `present` (default) | Creates the ACL if it is missing, sends the rules, then binds it if it is not bound. |
| `absent` | Unbinds the ACL if bound, removes it if present, then stops. |
| `unbind` | Unbinds the ACL if bound, then stops. The ACL and its rules stay on the switch. |
| `update` | Unbinds the ACL if bound, removes it, recreates it, sends the rules, then binds it. |

## ACL options

`acls` is a single dictionary (not a list). Give it for every state; in practice only `id` is needed for `absent` and `unbind`.

| Option | Type | Effect |
|---|---|---|
| `id` | str, required | ACL number, e.g. `"1001"`. Quote it so YAML keeps it a string. |
| `name` | str | ACL name. Sent as `name "<name>"` when the ACL is created. |
| `vid` | int | VLAN the ACL is bound to. Also added to each rule when `rule_type` is `combined`. |
| `rule_type` | `ip` / `combined` | ACL type. Required whenever you give `rules`: it is used to build each rule command. |
| `rules` | list of dict | Rules to send, in the order given. |

### Rule options

| Option | Type | Effect |
|---|---|---|
| `seq` | int, required | Rule sequence number. |
| `action` | `permit` / `deny` | Default `permit`. |
| `logging` | `enable` / `disable` | Default `disable`. See Limitations. |
| `sip`, `sip_mask` | str | Source IP and mask. Sent only when **both** are set. |
| `dip`, `dip_mask` | str | Destination IP and mask. Sent only when **both** are set. |
| `protocol` | int | IP protocol number. |
| `protocol_name` | str | `ICMP`, `IGMP`, `TCP`, `UDP`, `IPV6`, `ESP`, `AH` or `OSPF`. Converted to its number. |
| `dport` | int | Destination port. Sent only when the protocol is TCP (6) or UDP (17). |
| `dport_mask` | int | Destination port mask. Defaults to `0000` when `dport` is sent without it. |

`protocol` and `protocol_name` are mutually exclusive.

## Binding behavior

- With `vid`, the ACL is bound to that VLAN: `access-list bind <id> interface vlan <vid>`.
- Without `vid`, the bind command is `access-list bind <id>` only, with no target.
- A bind is skipped when the ACL is already bound (`ACL <id> is already bound.`).
- `absent`, `unbind` and `update` unbind with `no access-list bind <id>`, but only if the ACL is bound.
- `present` never unbinds.

## What happens on each run

1. **Collect.** The module enters config mode, then reads `show access-list bind` and `show access-list`. This tells it whether the ACL is bound and whether it exists.
2. **Unbind.** Skipped for `present`.
   - `unbind` ends the run here.
3. **Remove.** For `absent` and `update`, sends `no access-list create <id>` if the ACL exists.
   - `absent` ends the run here.
4. **Create.** For `present` and `update`, sends `access-list create <id>` (with the name, if given) if the ACL does not exist. With `present` on an existing ACL this step does nothing.
5. **Rules.** With no `rules`, nothing is sent. Otherwise one `access-list <rule_type> <id> rule <seq> <action> ...` command is sent per rule. The module waits 5 seconds after each rule.
6. **Bind.** See Binding behavior.

The module does not re-read the switch to verify the result.

## Check mode

`--check` reads the switch and reports what would be done, but sends no commands. Step messages read `would be unbound`, `would be removed`, `would be created`, `would be configured` or `would be bound`. `changed` stays `false` and `cmd` is empty.

`state: update` in check mode fails when the ACL already exists, because the removal is not simulated and the create step then finds the ACL still present. Use `--check` with `present`, `absent` or `unbind` only.

## Return values

| Key | When | Contents |
|---|---|---|
| `changed` | always | `true` if any command was sent. |
| `msg` | always | Message from the last step. |
| `switch` | always | Host the module connected to. |
| `check_mode` | always | Whether the run was in check mode. |
| `current_state` | always | Name of the last step run. |
| `cmd` | always | The last command sent. |
| `steps` | always | One entry per step: `step`, `name`, `changed`, `msg`. |
| `acl_info` | `-vv` and up | `acl_id`, plus `bound_state` and `state` each with `starting` and `finished` values (bound / present). |
| `steps` (extended) | `-vvv` and up | Each step also carries its `command` and an `acl_info` block (`id`, `is_bound`, `was_bound`, `is_present`, `was_present`). |
| `commands_sent` | `-vvvv` | Every command sent. |

Step names are `unbind_acl`, `remove_acl`, `create_and_update_acl`, `create_and_update_acl_rules` and `bind_acls`. Steps that run depend on `state`.

## Errors

| Message | Cause |
|---|---|
| `ACL <id> should not be present on the system when updating. This may indicate a logic error.` | `state: update` in check mode on an existing ACL (see Check mode). |
| `Unknown protocol name: <name>` | A `protocol_name` the module cannot map to a number. |
| `Unexpected state '<state>' for ACL <id>.` | Internal guard; not reachable with the allowed `state` choices. |

Other failures (SSH, authentication, timeouts, a command the switch rejects) are reported with the underlying exception text as `msg`.

## Limitations

- **Not idempotent for rules.** With `present` the rule commands are sent on every run, so `changed` is `true` each time rules are given. Rules already on the switch are not compared, and rules you leave out are not removed. Use `update` to rebuild the ACL from exactly your rules.
- **`update` drops and recreates the ACL.** It is unbound and removed first, so it is briefly absent from the switch.
- **`logging` is sent as `enable` whenever it has a value.** The code tests the option for truthiness, and `disable` is a non-empty string. So `logging: disable`, and the default, produce `logging enable`. Verified from the code only, not on a switch.
- **`acls` is needed in practice.** The module builds the ACL from it before checking `state`, so omit it only if you accept a failure.
- **Rules are slow.** Each rule is followed by a 5-second wait.
- **Saving is separate.** Changes are made to the running config. Use `jetstream_save` to persist them.
