#!/usr/bin/python
# -*- coding: utf-8 -*-
# MIT License (see LICENSE)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: jetstream_user
short_description: Manage local user accounts on TP-Link JetStream switches
description:
  - Connects to a TP-Link JetStream (Omada) switch over SSH using Netmiko.
  - Manages local user accounts, privilege levels, passwords, and user deletion.
  - Supports both password and MD5 secret configuration with plain or encrypted keys.
  - Optionally persists running configuration to startup configuration.
version_added: "0.1.0"
author:
  - Lachlan Stone (@lachlanstone)
requirements:
  - netmiko
options:
  host:
    description: Hostname or IP address of the switch.
    type: str
    required: true
  port:
    description: SSH port of the switch.
    type: int
    default: 22
  username:
    description: SSH username used to authenticate with the switch.
    type: str
    required: true
  password:
    description: SSH password used to authenticate with the switch.
    type: str
    default: ""
  enable_password:
    description: Password for privileged (enable) mode.
    type: str
    default: ""
  name:
    description:
      - Username of the account to configure or remove.
      - Maximum 16 characters; alphanumeric and permitted symbols; no spaces.
    type: str
  privilege:
    description:
      - Privilege level granted to the user.
      - Older models primarily support C(admin) and C(guest).
      - Newer Omada/JetStream models support C(admin), C(operator), C(power_user), and C(user).
    type: str
    choices: [admin, guest, operator, power_user, user]
    default: admin
  password_type:
    description:
      - Specifies whether to configure a standard password or an MD5 hashed secret.
      - C(secret) is recommended for improved encryption storage.
    type: str
    choices: [secret, password]
    default: secret
  encryption_type:
    description:
      - Specifies the encryption format of the supplied password string.
      - C(0) indicates plaintext input (encrypted by the switch).
      - C(5) indicates an already-encrypted MD5 secret.
      - C(7) indicates an already-encrypted password.
    type: int
    choices: [0, 5, 7]
    default: 0
  user_password:
    description:
      - Password or secret string for the user account.
      - Required when C(state=present) for a new user account.
    type: str
  state:
    description:
      - Desired state of the user account.
      - C(present) creates or updates the user account.
      - C(absent) removes the user account.
    type: str
    choices: [present, absent]
    default: present
  update_password:
    description:
      - C(always) will update the user and password even if the user already exists.
      - C(on_create) will only configure the user if they do not already exist.
    type: str
    choices: [always, on_create]
    default: always
  save_config:
    description:
      - Automatically saves running configuration to startup configuration when changes are made.
    type: bool
    default: false
  users:
    description:
      - A list of user account definitions to configure in batch.
      - Can be used instead of or alongside the single-user parameters.
    type: list
    elements: dict
    suboptions:
      name:
        description: Username of the account.
        type: str
        required: true
      privilege:
        description: Privilege level for this user.
        type: str
        choices: [admin, guest, operator, power_user, user]
        default: admin
      password_type:
        description: Storage type (C(secret) or C(password)).
        type: str
        choices: [secret, password]
        default: secret
      encryption_type:
        description: Encryption level of the supplied password (0=plain, 5=MD5, 7=reversible).
        type: int
        choices: [0, 5, 7]
        default: 0
      password:
        description: Password or secret string.
        type: str
      state:
        description: Desired state of this user account.
        type: str
        choices: [present, absent]
        default: present
      update_password:
        description:
          - C(always) will update the user and password even if the user already exists.
          - C(on_create) will only configure the user if they do not already exist.
        type: str
        choices: [always, on_create]
        default: always
notes:
  - Supports check mode.
  - Accounts with lower privilege levels (operator, power_user, user) may require switch enable password configuration to execute privileged commands.
"""

EXAMPLES = r"""
- name: Create an administrative user with encrypted secret
  lachlanstone.jetstream.jetstream_user:
    host: 192.0.2.10
    username: admin
    password: "{{ vault_switch_password }}"
    enable_password: "{{ vault_switch_enable_password }}"
    name: netops
    privilege: admin
    password_type: secret
    encryption_type: 0
    user_password: "{{ vault_netops_password }}"
    state: present

- name: Create a read-only guest user
  lachlanstone.jetstream.jetstream_user:
    host: 192.0.2.10
    username: admin
    password: "{{ vault_switch_password }}"
    enable_password: "{{ vault_switch_enable_password }}"
    name: guest_audit
    privilege: guest
    password_type: password
    encryption_type: 0
    user_password: "{{ vault_guest_password }}"
    state: present

- name: Remove a user account
  lachlanstone.jetstream.jetstream_user:
    host: 192.0.2.10
    username: admin
    password: "{{ vault_switch_password }}"
    enable_password: "{{ vault_switch_enable_password }}"
    name: temp_user
    state: absent

- name: Batch configure user accounts
  lachlanstone.jetstream.jetstream_user:
    host: 192.0.2.10
    username: admin
    password: "{{ vault_switch_password }}"
    enable_password: "{{ vault_switch_enable_password }}"
    users:
      - name: netops
        privilege: admin
        password_type: secret
        password: "{{ vault_netops_password }}"
        state: present
      - name: monitor
        privilege: guest
        password_type: password
        password: "{{ vault_monitor_password }}"
        state: present
      - name: old_admin
        state: absent
"""

RETURN = r"""
msg:
  description: Summary message of the user management operations.
  returned: always
  type: str
switch:
  description: Host IP or hostname the module connected to.
  returned: always
  type: str
changed:
  description: Whether any user configuration command was sent to the switch.
  returned: always
  type: bool
check_mode:
  description: Whether the module executed in check mode.
  returned: always
  type: bool
cmd:
  description: Last command sent to the switch, with the account password redacted.
  returned: always
  type: str
steps:
  description: Per-step operation results recorded by ResultCollector.
  returned: always
  type: list
  elements: dict
"""

import logging
from ansible.module_utils.basic import AnsibleModule
from netmiko import ConnectHandler

try:
    from ansible_collections.lachlanstone.jetstream.plugins.module_utils.send_command import (
        send_command,
    )
    from ansible_collections.lachlanstone.jetstream.plugins.module_utils.collector import (
        ResultCollector,
    )
except ImportError:
    from plugins.module_utils.send_command import send_command
    from plugins.module_utils.collector import ResultCollector

# Configure logging for Netmiko
logger = logging.getLogger(name="netmiko")
logger.setLevel(level=logging.DEBUG)
logger.propagate = False
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logging_enabled = True
if logging_enabled:
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level=logging.INFO)
    stream_handler.setFormatter(fmt=formatter)
    logger.addHandler(hdlr=stream_handler)


def parse_user_output(output):
    """Parse existing user accounts from switch CLI output.

    Supports both key-value format (show user configuration) and table format
    (show user account-list).
    """
    users = {}
    if not output:
        return users

    current_user = None
    for line in output.splitlines():
        line_clean = line.strip()
        if not line_clean or line_clean.startswith("---") or line_clean.startswith("==="):
            continue

        # Format 1: Key-value lines (e.g., 'User Name: admin')
        if ":" in line_clean:
            key, _, val = line_clean.partition(":")
            key = key.strip().lower()
            val = val.strip()
            if key in ("user name", "username", "name"):
                current_user = val
                if current_user not in users:
                    users[current_user] = {}
            elif current_user and key in ("privilege", "privilege level"):
                users[current_user]["privilege"] = val.lower()
            elif current_user and key in ("status", "state"):
                users[current_user]["status"] = val.lower()
            continue

        # Format 2: Tabular whitespace-separated columns
        parts = line_clean.split()
        if len(parts) >= 2:
            first = parts[0].lower()
            if first in ("user", "username", "name"):  # Header row
                continue
            uname = parts[0]
            priv = parts[1].lower()
            if priv in ("admin", "guest", "operator", "power_user", "user"):
                users[uname] = {
                    "privilege": priv,
                    "status": parts[2].lower() if len(parts) > 2 else "enable",
                }

    return users


def read_existing_users(net_connect):
    """Query the switch for currently configured user accounts."""
    for cmd in ("show user configuration", "show user account-list"):
        try:
            output = send_command(net_connect, cmd=cmd)
            if output and "Invalid input" not in output and "Incomplete command" not in output:
                users = parse_user_output(output)
                if users:
                    return users
        except Exception:
            continue
    return {}


def manage_users(net_connect, user_entries, collector, check_mode=False):
    """Apply desired user configurations or deletions on the switch."""
    initial_existing = read_existing_users(net_connect) if net_connect else None
    existing_users = dict(initial_existing) if initial_existing is not None else {}
    changed = False

    for entry in user_entries:
        name = entry.get("name")
        if not name:
            continue

        if len(name) > 16 or " " in name:
            raise ValueError(
                f"Invalid username '{name}': maximum 16 characters and no spaces allowed."
            )

        state = entry.get("state", "present")
        privilege = entry.get("privilege", "admin")
        password_type = entry.get("password_type", "secret")
        encryption_type = entry.get("encryption_type", 0)
        password = entry.get("password")
        update_password = entry.get("update_password", "always")

        user_exists = name in existing_users
        current_priv = existing_users.get(name, {}).get("privilege")

        if state == "absent":
            if initial_existing is not None and not user_exists:
                logger.info("User '%s' does not exist, skipping removal.", name)
                continue

            cmd = f"no user name {name}"
            msg = f"Removed user '{name}'"
            if check_mode:
                logger.info("Check mode: would remove user '%s' with command: %s", name, cmd)
            else:
                logger.info("Removing user '%s' with command: %s", name, cmd)
                send_command(net_connect, cmd=cmd)

            changed = True
            collector.add_step(
                name="remove_user",
            step_result={
                "changed": True,
                "msg": msg,
                "commands": [cmd],
                "commands_sent": [] if check_mode else [cmd],
                "command": cmd,
            },
            )
            if name in existing_users:
                del existing_users[name]

        elif state == "present":
            if user_exists and current_priv == privilege and update_password == "on_create":
                logger.info(
                    "User '%s' already exists with privilege '%s' and update_password=on_create; skipping.",
                    name,
                    privilege,
                )
                continue

            if not password and not user_exists:
                raise ValueError(f"Password is required to create new user '{name}'.")

            if not password and user_exists and update_password == "always":
                raise ValueError(
                    f"Password must be specified when updating user '{name}' on JetStream switch CLI."
                )

            if password:
                cmd = f"user name {name} privilege {privilege} {password_type} {encryption_type} {password}"
                safe_cmd = cmd[:-len(password)] + "<redacted>"
            else:
                cmd = f"user name {name} privilege {privilege}"
                safe_cmd = cmd

            action_desc = "Updated" if user_exists else "Created"
            msg = f"{action_desc} user '{name}' with privilege '{privilege}'"

            if check_mode:
                logger.info("Check mode: would configure user '%s' with command: %s", name, safe_cmd)
            else:
                logger.info("Configuring user '%s' with command: %s", name, safe_cmd)
                send_command(net_connect, cmd=cmd)

            changed = True
            collector.add_step(
                name="configure_user",
            step_result={
                "changed": True,
                "msg": msg,
                "commands": [safe_cmd],
                "commands_sent": [] if check_mode else [safe_cmd],
                "command": safe_cmd,
            },
            )
            existing_users[name] = {"privilege": privilege, "status": "enable"}

    return changed


def run_module(module):
    """Connect to the switch and execute user management operations."""
    device = {
        "device_type": "tplink_jetstream",
        "host": module.params["host"],
        "port": module.params["port"],
        "username": module.params["username"],
        "password": module.params["password"],
        "secret": module.params["enable_password"],
    }

    collector = ResultCollector()
    collector.set_basic_info(
        switch=module.params["host"],
        check_mode=module.check_mode,
        verbosity=module._verbosity,
    )

    user_entries = []
    if module.params.get("name"):
        user_entries.append(
            {
                "name": module.params["name"],
                "privilege": module.params.get("privilege", "admin"),
                "password_type": module.params.get("password_type", "secret"),
                "encryption_type": module.params.get("encryption_type", 0),
                "password": module.params.get("user_password"),
                "state": module.params.get("state", "present"),
                "update_password": module.params.get("update_password", "always"),
            }
        )

    if module.params.get("users"):
        for u in module.params["users"]:
            user_entries.append(
                {
                    "name": u.get("name"),
                    "privilege": u.get("privilege", "admin"),
                    "password_type": u.get("password_type", "secret"),
                    "encryption_type": u.get("encryption_type", 0),
                    "password": u.get("password"),
                    "state": u.get("state", "present"),
                    "update_password": u.get("update_password", "always"),
                }
            )

    if not user_entries:
        collector.add_step(
            name="manage_users",
            step_result={
                "changed": False,
                "msg": "No user accounts specified to configure.",
                "commands_sent": [],
            },
        )
        result = collector.return_info()
        module.exit_json(**result)

    with ConnectHandler(**device) as net_connect:
        net_connect.enable()
        net_connect.config_mode()
        changed = manage_users(
            net_connect=net_connect,
            user_entries=user_entries,
            collector=collector,
            check_mode=module.check_mode,
        )
        if module.params.get("save_config") and changed and not module.check_mode:
            send_command(net_connect, cmd="copy running-config startup-config")
            collector.add_step(
                name="save_config",
                step_result={
                    "changed": True,
                    "msg": "Saved running-config to startup-config",
                    "commands": ["copy running-config startup-config"],
                    "commands_sent": ["copy running-config startup-config"],
                    "command": "copy running-config startup-config",
                },
            )

    result = collector.return_info()
    module.exit_json(**result)


def main():
    """Ansible module argument specification and entry point."""
    module = AnsibleModule(
        argument_spec={
            "host": {"type": "str", "required": True},
            "port": {"type": "int", "default": 22},
            "username": {"type": "str", "required": True},
            "password": {"type": "str", "no_log": True, "default": ""},
            "enable_password": {"type": "str", "no_log": True, "default": ""},
            "name": {"type": "str", "required": False, "default": None},
            "privilege": {
                "type": "str",
                "required": False,
                "default": "admin",
                "choices": ["admin", "guest", "operator", "power_user", "user"],
            },
            "password_type": {
                "type": "str",
                "required": False,
                "default": "secret",
                "choices": ["secret", "password"],
            },
            "encryption_type": {
                "type": "int",
                "required": False,
                "default": 0,
                "choices": [0, 5, 7],
            },
            "user_password": {"type": "str", "required": False, "default": None, "no_log": True},
            "state": {
                "type": "str",
                "required": False,
                "default": "present",
                "choices": ["present", "absent"],
            },
            "update_password": {
                "type": "str",
                "required": False,
                "default": "always",
                "choices": ["always", "on_create"],
            },
            "save_config": {"type": "bool", "required": False, "default": False},
            "users": {
                "type": "list",
                "elements": "dict",
                "required": False,
                "default": None,
                "options": {
                    "name": {"type": "str", "required": True},
                    "privilege": {
                        "type": "str",
                        "required": False,
                        "default": "admin",
                        "choices": ["admin", "guest", "operator", "power_user", "user"],
                    },
                    "password_type": {
                        "type": "str",
                        "required": False,
                        "default": "secret",
                        "choices": ["secret", "password"],
                    },
                    "encryption_type": {
                        "type": "int",
                        "required": False,
                        "default": 0,
                        "choices": [0, 5, 7],
                    },
                    "password": {"type": "str", "required": False, "default": None, "no_log": True},
                    "state": {
                        "type": "str",
                        "required": False,
                        "default": "present",
                        "choices": ["present", "absent"],
                    },
                    "update_password": {
                        "type": "str",
                        "required": False,
                        "default": "always",
                        "choices": ["always", "on_create"],
                    },
                },
            },
        },
        supports_check_mode=True,
    )

    try:
        run_module(module)
    except Exception as e:
        module.fail_json(msg=str(e), exception=e, check_mode=module.check_mode)


if __name__ == "__main__":
    main()
