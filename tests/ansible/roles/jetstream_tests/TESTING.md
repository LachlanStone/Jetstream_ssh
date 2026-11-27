# Jetstream Collection — Integration Test Role

## Overview

The `jetstream_tests` role provides a comprehensive suite of integration tests for every module in the `lachlanstone.jetstream` Ansible collection. Tests run directly against a physical or lab TP-Link JetStream (Omada) switch over SSH.

The role is designed so:

- Nothing runs unless explicitly tagged — all tasks carry `never` by default.
- Happy path tests confirm correct behaviour and validate return structure.
- Bad data tests confirm the module fails correctly when given invalid input.
- Teardown blocks clean up all test state from the switch after each module's tests.
- ACL IDs and usernames are isolated in a high range to avoid production collisions.

---

## Directory Structure

```
tests/ansible/
├── ansible.cfg                          # Ansible configuration
├── inventory.ini                        # Switch inventory
├── group_vars/switch.yml                # Connection credentials
├── test_jetstream_role.yml              # Entry playbook
└── roles/
    └── jetstream_tests/
        ├── meta/main.yml                # Role metadata
        ├── defaults/main.yml            # Test fixtures (overridable)
        ├── vars/main.yml                # Fixed constants
        └── tasks/
            ├── main.yml                 # Orchestrator — includes each module file
            ├── command.yml              # jetstream_command tests
            ├── system.yml               # jetstream_system tests
            ├── vlans.yml                # jetstream_vlans tests
            ├── interfaces.yml           # jetstream_interfaces tests
            ├── user.yml                 # jetstream_user tests
            ├── acls.yml                 # jetstream_acls tests
            └── save.yml                 # jetstream_save tests
```

---

## Configuration

### Credentials — `group_vars/switch.yml`

```yaml
switch_host: 10.10.10.50
ssh_port: 22
ssh_username: admin
ssh_password: password
ssh_enable_password: password
```

These feed into the role defaults automatically. Override them per host as needed.

### Test Fixtures — `defaults/main.yml`

All test-specific values (interface names, VLAN IDs, ACL IDs, usernames) live in `defaults/main.yml`. Override them in `group_vars`, `host_vars`, or directly in the playbook `vars` block before running.

Key defaults to review before first run:

| Variable | Default | Purpose |
|---|---|---|
| `test_iface_primary` | `1/0/1` | Port used for interface tests |
| `test_iface_port_type` | `two-gigabitEthernet` | Port type for test switch |
| `test_vlans` | IDs 910–930 | VLANs created during tests |
| `test_acl_ids.*` | 1901–1905, 1999 | ACL IDs used — must not exist in production config |
| `test_users.*` | `ts_admin`, `ts_guest` etc. | Usernames created — prefixed `ts_` to avoid collision |

---

## Running Tests

### Prerequisites

```bash
pip install -r requirements.txt        # netmiko and dependencies
ansible-galaxy collection install lachlanstone.jetstream
```

### Run the full suite

```bash
cd tests/ansible
ansible-playbook test_jetstream_role.yml --tags all_modules
```

### Run a single module

```bash
ansible-playbook test_jetstream_role.yml --tags jetstream_command
ansible-playbook test_jetstream_role.yml --tags jetstream_system
ansible-playbook test_jetstream_role.yml --tags jetstream_vlans
ansible-playbook test_jetstream_role.yml --tags jetstream_interfaces
ansible-playbook test_jetstream_role.yml --tags jetstream_user
ansible-playbook test_jetstream_role.yml --tags jetstream_acls
ansible-playbook test_jetstream_role.yml --tags jetstream_save
```

### Run only bad-data / failure tests

```bash
ansible-playbook test_jetstream_role.yml --tags bad_data
```

### Run a specific sub-test

```bash
ansible-playbook test_jetstream_role.yml --tags acls_present
ansible-playbook test_jetstream_role.yml --tags sys_idempotent
ansible-playbook test_jetstream_role.yml --tags user_teardown
ansible-playbook test_jetstream_role.yml --tags vlans_boundary
```

### Verbose output

Ansible verbosity maps to the `ResultCollector` detail level inside the modules:

| Flag | Verbosity | Extra output |
|---|---|---|
| (none) | 0 | `msg`, `switch`, `changed`, `cmd`, basic `steps` |
| `-v` | 1 | Same |
| `-vv` | 2 | `acl_info`, `system_info` added to result |
| `-vvv` | 3 | Full `steps` list including per-command detail |
| `-vvvv` | 4 | `commands_sent` list added |

```bash
ansible-playbook test_jetstream_role.yml --tags jetstream_acls -vvv
```

---

## Tag Reference

### Module-level tags

| Tag | Runs |
|---|---|
| `all_modules` | All 7 module test files |
| `jetstream_command` | `command.yml` |
| `jetstream_system` | `system.yml` |
| `jetstream_vlans` | `vlans.yml` |
| `jetstream_interfaces` | `interfaces.yml` |
| `jetstream_user` | `user.yml` |
| `jetstream_acls` | `acls.yml` |
| `jetstream_save` | `save.yml` |

### Cross-cutting tags

| Tag | Runs |
|---|---|
| `bad_data` | All failure/negative tests across all modules |
| `never` | (internal) prevents accidental execution without an explicit tag |

### Sub-test tags (selected)

**command.yml**
`cmd_single`, `cmd_multi`, `cmd_cli_level`, `cmd_config_level`, `cmd_fallback`, `cmd_override`, `cmd_check_mode`, `cmd_return_structure`

**system.yml**
`sys_hostname`, `sys_location`, `sys_contact`, `sys_identity_all`, `sys_idempotent`, `sys_dns`, `sys_lldp`, `sys_ntp`, `sys_ntp_5servers`, `sys_all`, `sys_check_mode`

**vlans.yml**
`vlans_named`, `vlans_static_ip`, `vlans_dhcp`, `vlans_boundary`, `vlans_check_mode`

**interfaces.yml**
`iface_port_type`, `iface_full`, `iface_speed`, `iface_enabled`, `iface_pvid`, `iface_frame_type`, `iface_description`, `iface_fq_name`, `iface_multi`, `iface_check_mode`

**user.yml**
`user_priv_admin`, `user_priv_guest`, `user_priv_operator`, `user_priv_power`, `user_priv_user`, `user_on_create`, `user_always`, `user_security`, `user_bulk`, `user_both`, `user_save_config`, `user_check_mode`, `user_absent`, `user_teardown`

**acls.yml**
`acls_setup`, `acls_present`, `acls_tcp`, `acls_idempotent`, `acls_ip_type`, `acls_protocols`, `acls_misc_protocols`, `acls_dport_mask`, `acls_dport_nomask`, `acls_icmp_dport`, `acls_update`, `acls_unbind`, `acls_check_mode`, `acls_teardown`

**save.yml**
`save_default`, `save_write`, `save_check_mode`, `save_return_structure`

---

## Module Test Coverage

### `jetstream_command` (17 tasks, 9 assertions)

| Test | Tag |
|---|---|
| Single command at enable level | `cmd_single` |
| Multiple commands at enable level | `cmd_multi` |
| `command_level: cli` | `cmd_cli_level` |
| `command_level: config` | `cmd_config_level` |
| Neither command nor commands — falls back to `show system-info` | `cmd_fallback` |
| `commands` overrides `command` when both set | `cmd_override` |
| Check mode exits without running | `cmd_check_mode` |
| Return structure: `commands[]`, `stdout`, `stdout_lines`, `textfsm_parsed` | `cmd_return_structure` |
| **[bad]** Invalid `command_level` choice | `bad_data` |

---

### `jetstream_system` (39 tasks, 19 assertions)

| Test | Tag |
|---|---|
| Set hostname only | `sys_hostname` |
| Set location only | `sys_location` |
| Set contact only | `sys_contact` |
| Set all three together | `sys_identity_all` |
| Idempotency — same hostname twice, second run `changed: false` | `sys_idempotent` |
| DNS primary only | `sys_dns` |
| DNS primary + secondary | `sys_dns` |
| LLDP enable | `sys_lldp` |
| LLDP disable + restore | `sys_lldp` |
| NTP with 2 servers (minimum) | `sys_ntp` |
| NTP with 5 servers (maximum) | `sys_ntp_5servers` |
| All params combined | `sys_all` |
| Check mode — `changed: false`, `check_mode: true` | `sys_check_mode` |
| **[bad]** DNS secondary without primary → fail | `bad_data` |
| **[bad]** NTP `type: manual` → silently skipped, `changed: false` | `bad_data` |
| **[bad]** NTP missing `ntp_utc` → fail | `bad_data` |
| **[bad]** NTP only 1 server → fail | `bad_data` |
| **[bad]** NTP missing `ntp_fetch_time` → fail | `bad_data` |
| **[bad]** Empty `system: {}` → clean exit, no changes | `bad_data` |

---

### `jetstream_vlans` (22 tasks, 11 assertions)

| Test | Tag |
|---|---|
| Named VLANs (IDs 910–930) | `vlans_named` |
| Static IP SVI | `vlans_static_ip` |
| DHCP SVI | `vlans_dhcp` |
| Boundary: `vlan_id: 1` | `vlans_boundary` |
| Boundary: `vlan_id: 4094` | `vlans_boundary` |
| Check mode — `changed: false` | `vlans_check_mode` |
| **[bad]** `vlan_id: 0` → fail | `bad_data` |
| **[bad]** `vlan_id: 4095` → fail | `bad_data` |
| **[bad]** `ip_address` + `ip_dhcp` together → fail | `bad_data` |
| **[bad]** `ip_address` without `subnet_mask` → fail | `bad_data` |
| **[bad]** Empty `vlans: []` → clean exit, `changed: false` | `bad_data` |

---

### `jetstream_interfaces` (37 tasks, 18 assertions)

| Test | Tag |
|---|---|
| `port_type: gigabitEthernet` | `iface_port_type` |
| `port_type: two-gigabitEthernet` — full feature set | `iface_full` |
| `port_type: ten-gigabitEthernet` | `iface_port_type` |
| `port_type: fastEthernet` | `iface_port_type` |
| Speed choices: `1000`, `auto` | `iface_speed` |
| `enabled: false` → shutdown | `iface_enabled` |
| `enabled: true` → no shutdown + restore | `iface_enabled` |
| PVID + untagged + tagged + disabled VLANs | `iface_pvid` |
| `acceptable_frame_type: tagged` + restore to `all` | `iface_frame_type` |
| Description with spaces (quoted in CLI) | `iface_description` |
| Description without spaces (unquoted) | `iface_description` |
| Fully-qualified interface name passed through unchanged | `iface_fq_name` |
| Multiple interfaces in one call | `iface_multi` |
| Check mode — `changed: false` | `iface_check_mode` |
| **[bad]** Unknown `port_type` → fail | `bad_data` |
| **[bad]** Invalid `speed` choice → fail | `bad_data` |
| **[bad]** Invalid `acceptable_frame_type` → fail | `bad_data` |
| **[bad]** Empty `interfaces: []` → clean exit | `bad_data` |

---

### `jetstream_user` (40 tasks, 20 assertions)

| Test | Tag |
|---|---|
| Create admin user (`privilege: admin`, `password_type: secret`, `encryption_type: 0`) | `user_priv_admin` |
| Create guest user (`privilege: guest`, `password_type: password`) | `user_priv_guest` |
| Create operator user | `user_priv_operator` |
| Create power_user | `user_priv_power` |
| Create standard user (`privilege: user`) | `user_priv_user` |
| `update_password: on_create` — existing user, same privilege → skipped | `user_on_create` |
| `update_password: always` — existing user → updated | `user_always` |
| Password never appears in `cmd` return value (redaction) | `user_security` |
| Batch `users` list (3 users, mixed privileges) | `user_bulk` |
| `name` top-level + `users` list simultaneously | `user_both` |
| `save_config: true` — save command issued after change | `user_save_config` |
| Check mode — `changed: false` | `user_check_mode` |
| `state: absent` — remove existing user | `user_absent` |
| `state: absent` — user already gone → `changed: false` | `user_absent` |
| Teardown — bulk remove all test users | `user_teardown` |
| **[bad]** Username > 16 characters → fail | `bad_data` |
| **[bad]** Username with spaces → fail | `bad_data` |
| **[bad]** `state: present`, new user, no password → fail | `bad_data` |
| **[bad]** Invalid `privilege` choice → fail | `bad_data` |
| **[bad]** Invalid `encryption_type` (3) → fail | `bad_data` |
| **[bad]** Neither `name` nor `users` → clean exit, `changed: false` | `bad_data` |

---

### `jetstream_acls` (35 tasks, 17 assertions)

| Test | Tag |
|---|---|
| Setup — remove stale test ACLs | `acls_setup` |
| `state: present`, `rule_type: combined`, TCP permit + deny, with `vid` | `acls_present` |
| Idempotency — `state: present` on already-present ACL → `changed: false` | `acls_idempotent` |
| `state: present`, `rule_type: ip`, protocol by number (89) | `acls_ip_type` |
| Protocol coverage — ICMP, UDP, ESP, AH | `acls_protocols` |
| Protocol coverage — IGMP, IPV6, OSPF | `acls_misc_protocols` |
| `dport_mask` explicitly provided | `acls_dport_mask` |
| `dport` without `dport_mask` → defaults to `0000` | `acls_dport_nomask` |
| ICMP rule with `dport` — `dport` silently ignored (not TCP/UDP) | `acls_icmp_dport` |
| `state: update` — full unbind → remove → recreate → rebind cycle | `acls_update` |
| `state: unbind` — detach bound ACL | `acls_unbind` |
| `state: unbind` — already unbound → `changed: false` | `acls_unbind` |
| Check mode — `changed: false`, no commands sent | `acls_check_mode` |
| Teardown — `state: absent` loop over all test ACL IDs | `acls_teardown` |
| **[bad]** `protocol` + `protocol_name` together → `mutually_exclusive` fail | `bad_data` |
| **[bad]** Invalid `protocol_name` (HTTP) → Ansible choice validation fail | `bad_data` |
| **[bad]** Invalid `state` (replace) → Ansible choice validation fail | `bad_data` |
| **[bad]** Invalid `action` (forward) → Ansible choice validation fail | `bad_data` |

---

### `jetstream_save` (10 tasks, 6 assertions)

| Test | Tag |
|---|---|
| Default command (`copy running-config startup-config`) | `save_default` |
| `command: write` | `save_write` |
| Check mode — `changed: false`, no connection made | `save_check_mode` |
| Return structure — all required keys present | `save_return_structure` |
| **[bad]** Invalid `command` choice (`save now`) → Ansible validation fail | `bad_data` |

---

## Return Structure Contract

Every module (except `jetstream_command`) returns these keys on every run:

| Key | Type | Notes |
|---|---|---|
| `msg` | str | Human-readable summary of the last step |
| `switch` | str | Host the module connected to |
| `changed` | bool | True if any configuration command was sent |
| `check_mode` | bool | True when run with `--check` |
| `cmd` | str | Last command sent (passwords redacted) |
| `steps` | list | Per-step results (detail expands with verbosity) |

`jetstream_command` returns `commands[]` instead, with each entry containing `command`, `stdout`, `stdout_lines`, `textfsm_parsed`, and optionally `parsed`.

---

## Writing New Tests

Follow this pattern for each test:

```yaml
- name: "[module] Brief description of what is being tested"
  lachlanstone.jetstream.jetstream_MODULE:
    host: "{{ test_host }}"
    port: "{{ test_port }}"
    username: "{{ test_username }}"
    password: "{{ test_password }}"
    enable_password: "{{ test_enable_password }}"
    # ... module params ...
  register: result_name
  tags: [jetstream_MODULE, specific_sub_tag, never]

- name: "[module] Assert description"
  ansible.builtin.assert:
    that:
      - result_name is not failed
      - result_name.changed == true        # or false
      # additional return value assertions
    fail_msg: "Description failed: {{ result_name.msg | default('no msg') }}"
  tags: [jetstream_MODULE, specific_sub_tag, never]
```

For bad data tests:

```yaml
- name: "[module][bad_data] Description of bad input"
  lachlanstone.jetstream.jetstream_MODULE:
    # ... intentionally invalid params ...
  register: bad_result
  ignore_errors: true
  tags: [jetstream_MODULE, bad_data, never]

- name: "[module][bad_data] Assert bad input caused failure"
  ansible.builtin.assert:
    that:
      - bad_result is failed
    fail_msg: "Expected failure but task succeeded"
  tags: [jetstream_MODULE, bad_data, never]
```

---

## Notes

- The `jetstream_vlans` and `jetstream_interfaces` modules do not read current state before writing. They always report `changed: true` when commands are sent. There is no `state: absent` for VLANs — VLANs created by the test suite persist on the switch.
- ACL tests use IDs 1901–1905 and 1999. These must not exist in your production configuration before running.
- User tests prefix all names with `ts_` and tear down on completion. The teardown uses `ignore_errors: true` so a partially completed run still cleans up what it can.
- The `jetstream_command` module does not support check mode and does not return `msg`/`switch`/`changed` in the standard shape — it returns a `commands[]` list.
