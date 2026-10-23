# TP-Link JetStream (Omada) Ansible collection

Ansible modules that configure TP-Link JetStream switches over SSH (Netmiko, `device_type: tplink_jetstream`).

## Modules

| Module | Purpose |
|---|---|
| `jetstream_acls` | Manage ACLs and rules |
| `jetstream_interfaces` | Configure interface ports |
| `jetstream_vlans` | Configure VLANs and SVIs |
| `jetstream_system` | Hostname, location, contact, DNS |
| `jetstream_user` | Manage local switch user accounts |
| `jetstream_save` | Save running configuration to startup configuration |
| `jetstream_command` | Run arbitrary CLI commands, optionally TextFSM-parsed |
Docs: `ansible-doc lachlanstone.jetstream.jetstream_acls`.

## Install

```bash
pip install -r requirements.txt
ansible-galaxy collection install lachlanstone.jetstream
```

## Example

```yaml
- hosts: localhost
  connection: local
  gather_facts: false
  tasks:
    - name: Run commands on a JetStream switch
      lachlanstone.jetstream.jetstream_command:
        host: "{{ lookup('env', 'SWITCH_HOST') }}"
        port: 22
        username: "{{ lookup('env', 'SSH_USERNAME') }}"
        password: "{{ lookup('env', 'SSH_PASSWORD') }}"
        enable_password: "{{ lookup('env', 'SSH_ENABLE_PASSWORD') }}"
        command_level: enable
        commands:
          - "show system-info"
```

Full playbook and variables: `docs/examples/`.

## TextFSM parsing

`jetstream_command` parses output with TextFSM when `NET_TEXTFSM` points at `extras/ntc_templates/`.
Only `show system-info` has a template.
