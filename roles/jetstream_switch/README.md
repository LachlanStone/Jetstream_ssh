# jetstream_switch

Role template that drives every module in the `lachlanstone.jetstream` collection to fully set up a TP-Link JetStream (Omada) switch over SSH.

## Requirements

* `lachlanstone.jetstream` collection (this collection)
* `netmiko` on the controller
* Network reachability from the controller to the switch (SSH)

## Role tasks (in order)

1. **System** – `jetstream_system`: hostname, location, contact, LLDP, DNS, NTP.
2. **Users** – `jetstream_user`: local accounts (privilege level, secrets, update policy).
3. **VLANs** – `jetstream_vlans`: VLANs and optional SVIs (static IP or DHCP).
4. **Interfaces** – `jetstream_interfaces`: state, description, speed, PVID, tagged/untagged VLANs.
5. **ACLs** – `jetstream_acls`: creation, rules, VLAN binding, removal (looped over `jetstream_acls`).
6. **Ad-hoc commands** – `jetstream_command`: any extra CLI commands.
7. **Save** – `jetstream_save`: persist running config to startup.

Each step can be skipped with its toggle (`jetstream_manage_*`).

## Role variables

Connection (see `defaults/main.yml`):

| Variable | Default |
|---|---|
| `jetstream_host` | `{{ inventory_hostname }}` |
| `jetstream_port` | `22` |
| `jetstream_username` | `admin` |
| `jetstream_password` | `""` |
| `jetstream_enable_password` | `""` |
| `jetstream_read_timeout` | `30` |

Feature toggles: `jetstream_manage_system`, `jetstream_manage_users`, `jetstream_manage_vlans`, `jetstream_manage_interfaces`, `jetstream_manage_acls`, `jetstream_save_config`.

Data variables: `jetstream_system`, `jetstream_lldp`, `jetstream_dns`, `jetstream_ntp`, `jetstream_users`, `jetstream_vlans`, `jetstream_interfaces`, `jetstream_acls` (+ `jetstream_acls_state`), `jetstream_commands` (+ `jetstream_command_level`), `jetstream_save_command`.

Shapes for each data variable match the module docs — see the DOCUMENTATION blocks in `plugins/modules/*.py` and the commented examples in `defaults/main.yml`.

## Example play

```yaml
- name: Configure access switches
  hosts: tp_link_jetstream
  gather_facts: false
  roles:
    - role: lachlanstone.jetstream.jetstream_switch
```

Example group/host vars:

```yaml
jetstream_username: ops
jetstream_password: "{{ vault_switch_password }}"
jetstream_enable_password: "{{ vault_switch_enable_password }}"

# Enable features to configure:
jetstream_manage_system: true
jetstream_manage_users: true
jetstream_manage_vlans: true
jetstream_manage_interfaces: true
jetstream_manage_acls: true

jetstream_system:
  hostname: sw-access-01
  location: "Bldg 1, IDC1"
  contact: "noc@example.com"
jetstream_lldp:
  enabled: true
jetstream_dns:
  primary: 10.0.0.1
  secondary: 10.0.0.2
jetstream_ntp:
  type: ntp
  ntp_utc: "+10:00"
  ntp_servers: [10.0.0.101, 10.0.0.102]
  ntp_fetch_time: 30

jetstream_users:
  - name: ops-admin
    privilege: admin
    password_type: secret
    encryption_type: 0
    password: "{{ vault_ops_admin_password }}"

jetstream_vlans:
  - vlan_id: 10
    name: MGMT
  - vlan_id: 20
    name: PRINTERS
    ip_address: 10.20.0.1
    subnet_mask: 255.255.255.0

jetstream_interfaces:
  - name: 1/0/1
    enabled: true
    description: "Uplink to core"
    vlans_tagged: [10, 20]

jetstream_acls:
  - id: "1001"
    name: ALLOW_PRINT
    vid: 20
    rule_type: combined
    rules:
      - seq: 10
        action: permit
        protocol_name: TCP
        dport: 9100
        sip: 10.20.0.0
        sip_mask: 255.255.255.0
```

A ready-made calling play lives in `extras/jetstream_switch_example.yml`.

## Notes

* All modules require `netmiko`; install with `pip install netmiko`.
* `check_mode` is supported by `jetstream_interfaces`, `jetstream_system`, `jetstream_user`, `jetstream_acls`, `jetstream_vlans` and `jetstream_save`.
* Change `jetstream_save_command` to `write` on firmware that does not accept `copy running-config startup-config`.
