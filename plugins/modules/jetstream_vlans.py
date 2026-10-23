#!/usr/bin/python
# -*- coding: utf-8 -*-
# MIT License (see LICENSE)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: jetstream_vlans
short_description: Configure VLANs and SVIs on TP-Link JetStream switches
description:
  - Connects to a TP-Link JetStream (Omada) switch over SSH with Netmiko and creates VLANs with an
    optional name and optional VLAN interface (SVI) address.
  - Commands are sent through the switch CLI, so the controller running the module needs network access to
    the switch. The module does not read the current VLAN state first, so it always reports a change when it
    sends commands.
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
  vlans:
    description: VLANs to configure.
    type: list
    elements: dict
    required: true
    suboptions:
      vlan_id:
        description: VLAN ID.
        type: int
        required: true
      name:
        description: VLAN name.
        type: str
      ip_address:
        description:
          - Static IP address for the VLAN interface.
          - Mutually exclusive with O(ip_dhcp).
        type: str
      subnet_mask:
        description: Dotted-decimal subnet mask for O(ip_address).
        type: str
      ip_dhcp:
        description:
          - Allocate the VLAN interface address over DHCP.
          - Mutually exclusive with O(ip_address).
        type: bool
        default: false
notes:
  - Supports check mode.
"""

EXAMPLES = r"""
- name: Configure a servers VLAN with a static SVI address
  lachlanstone.jetstream.jetstream_vlans:
    host: 192.0.2.10
    username: admin
    password: "{{ vault_switch_password }}"
    enable_password: "{{ vault_switch_enable_password }}"
    vlans:
      - vlan_id: 10
        name: Servers
        ip_address: 192.168.10.1
        subnet_mask: 255.255.255.0
      - vlan_id: 20
        name: Clients
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
  description: Per-VLAN step results; more detail is returned at higher Ansible verbosity.
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
from plugins.module_utils.config_mode import (
    CONFIG_PROMPT,
    ensure_global_config,
    require_config_mode,
)
from plugins.module_utils.vlans.vlan_builder import (
    build_vlan_commands,
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

# Entering `vlan ...` / `interface vlan ...` changes the prompt from (config)#
# to (config-vlan)# / (config-if)#; match all of them.
_CONFIG_PROMPT = CONFIG_PROMPT


def configure_vlan(net_connect, vlan, collector, check_mode):
    """Push one VLAN's commands to the device.

    Builds the CLI command list via ``build_vlan_commands``, then sends each
    command through the existing Netmiko session.  In check mode the
    commands are recorded but never sent.

    Args:
        net_connect: Active Netmiko connection (already in config mode).
        vlan (dict): One VLAN entry from ``module.params['vlans']``.
        collector (ResultCollector): Shared result accumulator.
        check_mode (bool): When True, skip sending; report what would change.
    """
    vlan_id = vlan["vlan_id"]
    cmds = build_vlan_commands(vlan)
    stdout_parts = []

    if check_mode:
        msg = f"VLAN {vlan_id}: would apply {len(cmds)} command(s)."
        logger.info(msg)
        collector.add_step(
            name=f"configure_vlan:{vlan_id}",
            step_result={
                "changed": False,
                "msg": msg,
                "commands": cmds,
                "settings": {key: value for key, value in vlan.items() if key != "vlan_id"},
                "stdout": "",
            },
        )
        return

    # Recover from a previous block that did not return to global config.
    ensure_global_config(net_connect)

    for cmd in cmds:
        if cmd == "exit":
            # JetStream does not reprint the prompt after `exit`; don't wait for one.
            output = net_connect.send_command_timing(cmd)
        else:
            output = send_command(net_connect, cmd, expect_string=_CONFIG_PROMPT)
        stdout_parts.append(f"# {cmd}\n{output}".strip())
        logger.info("Sent: %s | Output: %s", cmd, output.strip())

        # Context-entering commands must actually change the CLI mode.
        if cmd.startswith("interface vlan "):
            require_config_mode(
                net_connect, "interface", context=f"VLAN {vlan_id}"
            )
        elif cmd.startswith("vlan "):
            require_config_mode(net_connect, "vlan", context=f"VLAN {vlan_id}")

    collector.add_step(
        name=f"configure_vlan:{vlan_id}",
        step_result={
            "changed": True,
            "msg": f"VLAN {vlan_id} configured.",
            "commands": cmds,
            "commands_sent": cmds,
            "settings": {key: value for key, value in vlan.items() if key != "vlan_id"},
            "stdout": "\n".join(stdout_parts),
        },
    )


def run_module(module):
    """Open SSH connection and configure every requested VLAN."""
    device = build_device(module)

    collector = ResultCollector()
    collector.set_basic_info(
        switch=module.params["host"],
        check_mode=module.check_mode,
        verbosity=module._verbosity,
    )

    vlans = module.params.get("vlans") or []

    with ConnectHandler(**device) as net_connect:
        net_connect.enable()
        net_connect.config_mode()
        for vlan in vlans:
            configure_vlan(net_connect, vlan, collector, module.check_mode)

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
            "vlans": {
                "type": "list",
                "elements": "dict",
                "required": True,
                "options": {
                    "vlan_id": {"type": "int", "required": True},
                    "name": {"type": "str", "required": False, "default": None},
                    "ip_address": {"type": "str", "required": False, "default": None},
                    "subnet_mask": {"type": "str", "required": False, "default": None},
                    "ip_dhcp": {"type": "bool", "required": False, "default": False},
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
