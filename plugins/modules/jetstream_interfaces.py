#!/usr/bin/python
# -*- coding: utf-8 -*-
# MIT License (see LICENSE)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: jetstream_interfaces
short_description: Configure physical interfaces on TP-Link JetStream switches
description:
  - Connects to a TP-Link JetStream (Omada) switch over SSH with Netmiko and pushes per-interface settings
    such as speed, state, description, PVID and VLAN membership.
  - Commands are sent through the switch CLI, so the controller running the module needs network access to
    the switch. The module does not read the current interface state first, so it always reports a change
    when it sends commands.
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
    description: SSH username.
    type: str
    required: true
  password:
    description: SSH password.
    type: str
    default: ""
  enable_password:
    description: Password for privileged (enable) mode.
    type: str
    default: ""
  interfaces:
    description: Interfaces to configure.
    type: list
    elements: dict
    required: true
    suboptions:
      name:
        description: Port identifier such as V(1/0/1), or a fully qualified token such as V(gigabitEthernet 1/0/1).
        type: str
        required: true
      port_type:
        description: Interface type used to build the CLI interface token.
        type: str
        choices: [gigabitEthernet, two-gigabitEthernet, ten-gigabitEthernet, fastEthernet]
        default: gigabitEthernet
      speed:
        description: Port speed in Mbps, or V(auto).
        type: str
        choices: ["10", "100", "1000", "2500", "10000", auto]
      enabled:
        description: Whether the port is administratively enabled.
        type: bool
      description:
        description: Port description.
        type: str
      pvid:
        description: Port VLAN ID for untagged traffic.
        type: int
      vlans_untagged:
        description: VLAN IDs the port carries untagged.
        type: list
        elements: int
        default: []
      vlans_tagged:
        description: VLAN IDs the port carries tagged.
        type: list
        elements: int
        default: []
      vlans_disabled:
        description: VLAN IDs removed from the port.
        type: list
        elements: int
        default: []
      acceptable_frame_type:
        description: Frame types the port accepts.
        type: str
        choices: [all, tagged]
        default: all
notes:
  - Supports check mode.
"""

EXAMPLES = r"""
- name: Configure two access ports
  lachlanstone.jetstream.jetstream_interfaces:
    host: 192.0.2.10
    username: admin
    password: "{{ vault_switch_password }}"
    enable_password: "{{ vault_switch_enable_password }}"
    interfaces:
      - name: "1/0/9"
        description: Printer
        pvid: 10
        vlans_untagged: [10]
      - name: "1/0/10"
        enabled: false
"""

RETURN = r"""
msg:
  description: Summary message.
  returned: always
  type: str
switch:
  description: Host the module connected to.
  returned: always
  type: str
changed:
  description: Whether any configuration command was sent.
  returned: always
  type: bool
check_mode:
  description: Whether the module ran in check mode.
  returned: always
  type: bool
cmd:
  description: Last command sent to the switch.
  returned: always
  type: str
steps:
  description: Per-interface step results; more detail is returned at higher Ansible verbosity.
  returned: always
  type: list
  elements: dict
"""

import logging

from ansible.module_utils.basic import AnsibleModule
from netmiko import ConnectHandler

from plugins.module_utils.send_command import (
    send_command,
)
from plugins.module_utils.collector import (
    ResultCollector,
)
from plugins.module_utils.interfaces.interface_builder import (
    build_commands,
)
from plugins.module_utils.device import (
    build_device,
)


# ---------------------------------------------------------------------------
# Logging — same pattern as jetstream_system.py
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

# Entering `interface ...` changes the prompt from (config)# to (config-if)#; match both.
_CONFIG_PROMPT = r"\(config[^)]*\)#"


def configure_interface(net_connect, iface, collector, check_mode):
    """Push one interface's commands to the device.

    Builds the CLI command list via ``build_commands``, then sends each
    command through the existing Netmiko session.  In check mode the
    commands are recorded but never sent.

    Args:
        net_connect: Active Netmiko connection (already in config mode).
        iface (dict): One interface entry from ``module.params['interfaces']``.
        collector (ResultCollector): Shared result accumulator.
        check_mode (bool): When True, skip sending; report what would change.
    """
    name = iface["name"]
    cmds = build_commands(iface)
    stdout_parts = []

    if check_mode:
        msg = f"Interface {name}: would apply {len(cmds)} command(s)."
        logger.info(msg)
        collector.add_step(
            name=f"configure_interface:{name}",
            step_result={
                "changed": False,
                "msg": msg,
                "commands": cmds,
                "settings": {key: value for key, value in iface.items() if key != "name"},
                "stdout": "",
            },
        )
        return

    for cmd in cmds:
        if cmd == "exit":
            # JetStream does not reprint the prompt after `exit`; don't wait for one.
            output = net_connect.send_command_timing(cmd)
        else:
            output = send_command(net_connect, cmd, expect_string=_CONFIG_PROMPT)
        stdout_parts.append(f"# {cmd}\n{output}".strip())
        logger.info("Sent: %s | Output: %s", cmd, output.strip())

    collector.add_step(
        name=f"configure_interface:{name}",
        step_result={
            "changed": True,
            "msg": f"Interface {name} configured.",
            "commands": cmds,
            "commands_sent": cmds,
            "settings": {key: value for key, value in iface.items() if key != "name"},
            "stdout": "\n".join(stdout_parts),
        },
    )


def run_module(module):
    """Open SSH connection and configure every requested interface."""
    device = build_device(module)

    collector = ResultCollector()
    collector.set_basic_info(
        switch=module.params["host"],
        check_mode=module.check_mode,
        verbosity=module._verbosity,
    )

    interfaces = module.params.get("interfaces") or []

    with ConnectHandler(**device) as net_connect:
        net_connect.enable()
        net_connect.config_mode()
        for iface in interfaces:
            configure_interface(net_connect, iface, collector, module.check_mode)

    result = collector.return_info()
    module.exit_json(**result)


# ---------------------------------------------------------------------------
# Argument specification
# ---------------------------------------------------------------------------

def main():
    """Ansible module entry point."""
    module = AnsibleModule(
        argument_spec={
            "host": {"type": "str", "required": True},
            "port": {"type": "int", "default": 22},
            "username": {"type": "str", "required": True},
            "password": {"type": "str", "no_log": True, "default": ""},
            "enable_password": {"type": "str", "no_log": True, "default": ""},
            "interfaces": {
                "type": "list",
                "elements": "dict",
                "required": True,
                "options": {
                    "name": {"type": "str", "required": True},
                    "port_type": {
                        "type": "str",
                        "required": False,
                        "default": "gigabitEthernet",
                        "choices": [
                            "gigabitEthernet",
                            "two-gigabitEthernet",
                            "ten-gigabitEthernet",
                            "fastEthernet",
                        ],
                    },
                    "speed": {
                        "type": "str",
                        "required": False,
                        "default": None,
                        "choices": ["10", "100", "1000", "2500", "10000", "auto"],
                    },
                    "enabled": {
                        "type": "bool",
                        "required": False,
                        "default": None,
                    },
                    "description": {"type": "str", "required": False, "default": None},
                    "pvid": {"type": "int", "required": False, "default": None},
                    "vlans_untagged": {
                        "type": "list",
                        "elements": "int",
                        "required": False,
                        "default": [],
                    },
                    "vlans_tagged": {
                        "type": "list",
                        "elements": "int",
                        "required": False,
                        "default": [],
                    },
                    "vlans_disabled": {
                        "type": "list",
                        "elements": "int",
                        "required": False,
                        "default": [],
                    },
                    "acceptable_frame_type": {
                        "type": "str",
                        "required": False,
                        "default": "all",
                        "choices": ["all", "tagged"],
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
