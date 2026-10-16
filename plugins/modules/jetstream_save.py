#!/usr/bin/python
# -*- coding: utf-8 -*-
# MIT License (see LICENSE)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: jetstream_save
short_description: Save running configuration to startup configuration on TP-Link JetStream switches
description:
  - Connects to a TP-Link JetStream (Omada) switch over SSH using Netmiko.
  - Saves the active running configuration to persistent startup memory.
  - Uses C(copy running-config startup-config) by default, with optional support for the C(write) command.
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
  command:
    description:
      - The specific CLI command used to persist the running configuration.
      - C(copy running-config startup-config) is standard on JetStream and Omada switches.
      - C(write) is accepted by certain firmware releases.
    type: str
    choices:
      - "copy running-config startup-config"
      - "write"
    default: "copy running-config startup-config"
notes:
  - Supports check mode.
"""

EXAMPLES = r"""
- name: Save switch running configuration to startup configuration
  lachlanstone.jetstream.jetstream_save:
    host: 192.0.2.10
    username: admin
    password: "{{ vault_switch_password }}"
    enable_password: "{{ vault_switch_enable_password }}"

- name: Save switch configuration using the write command
  lachlanstone.jetstream.jetstream_save:
    host: 192.0.2.10
    username: admin
    password: "{{ vault_switch_password }}"
    enable_password: "{{ vault_switch_enable_password }}"
    command: "write"
"""

RETURN = r"""
msg:
  description: Summary message of the save operation.
  returned: always
  type: str
switch:
  description: Host IP or hostname the module connected to.
  returned: always
  type: str
changed:
  description: Whether the save command was executed.
  returned: always
  type: bool
check_mode:
  description: Whether the module executed in check mode.
  returned: always
  type: bool
cmd:
  description: The save command sent (or planned in check mode).
  returned: always
  type: str
steps:
  description: Operation steps recorded by ResultCollector.
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


def save_configuration(net_connect, cmd, collector, check_mode=False):
    """Save running configuration to startup configuration."""
    msg = f"Saved running-config to startup-config using '{cmd}'"

    if check_mode:
        logger.info("Check mode: would execute save command: %s", cmd)
        output = ""
    else:
        logger.info("Executing save command: %s", cmd)
        if hasattr(net_connect, "save_config"):
            output = net_connect.save_config(cmd=cmd)
        else:
            output = send_command(net_connect, cmd=cmd)

    collector.add_step(
        name="save_config",
        step_result={
            "changed": False if check_mode else True,
            "msg": msg,
            "commands": [cmd],
            "commands_sent": [cmd],
            "command": cmd,
            "stdout": output,
        },
    )
    return not check_mode


def run_module(module):
    """Connect to the switch and execute the save configuration operation."""
    cmd = module.params.get("command", "copy running-config startup-config")

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

    if module.check_mode:
        save_configuration(
            net_connect=None,
            cmd=cmd,
            collector=collector,
            check_mode=True,
        )
    else:
        with ConnectHandler(**device) as net_connect:
            net_connect.enable()
            save_configuration(
                net_connect=net_connect,
                cmd=cmd,
                collector=collector,
                check_mode=False,
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
            "command": {
                "type": "str",
                "required": False,
                "default": "copy running-config startup-config",
                "choices": ["copy running-config startup-config", "write"],
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
