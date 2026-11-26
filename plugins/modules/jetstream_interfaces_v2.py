#!/usr/bin/python
# -*- coding: utf-8 -*-
# MIT License (see LICENSE)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: jetstream_interfaces_v2
short_description: Configure physical interfaces on TP-Link JetStream switches (idempotent)
description:
  - Connects to a TP-Link JetStream (Omada) switch over SSH with Netmiko and pushes per-interface settings
    such as speed, state, description, PVID and VLAN membership.
  - Reads the current interface state first (C(show interface configuration) and C(show running-config))
    and only sends the commands for settings that differ, so it reports C(changed=false) when the
    interfaces already match the desired state.
  - Settings omitted from an C(interfaces) entry are left untouched.
version_added: "2.0.0"
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
  read_timeout:
    description:
      - Seconds Netmiko waits for the command prompt before raising a read timeout.
      - Defaults to C(JETSTREAM_READ_TIMEOUT) when set, otherwise 30.
    type: float
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
        description: Port speed in Mbps, or V(auto). Omit to leave the port speed untouched.
        type: str
        choices: ["10", "100", "1000", "2500", "10000", auto]
      enabled:
        description: Whether the port is administratively enabled. Omit to leave untouched.
        type: bool
      description:
        description:
          - Port description. Omit to leave untouched; an empty string clears the description.
        type: str
      pvid:
        description: Port VLAN ID for untagged traffic. Omit to leave untouched.
        type: int
      vlans_untagged:
        description: VLAN IDs the port carries untagged. Omit to leave untouched.
        type: list
        elements: int
        default: []
      vlans_tagged:
        description: VLAN IDs the port carries tagged. Omit to leave untouched.
        type: list
        elements: int
        default: []
      vlans_disabled:
        description: VLAN IDs removed from the port. Omit to leave untouched.
        type: list
        elements: int
        default: []
      acceptable_frame_type:
        description: Frame types the port accepts. Omit to leave untouched.
        type: str
        choices: [all, tagged]
notes:
  - Supports check mode.
"""

EXAMPLES = r"""
- name: Configure two access ports (idempotent)
  lachlanstone.jetstream.jetstream_interfaces_v2:
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
  description: Whether any configuration command was sent (or would be sent in check mode).
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

from ansible_collections.lachlanstone.jetstream.plugins.module_utils.send_command import (
    send_command,
)
from ansible_collections.lachlanstone.jetstream.plugins.module_utils.collector import (
    ResultCollector,
)
from ansible_collections.lachlanstone.jetstream.plugins.module_utils.config_mode import (
    CONFIG_PROMPT,
    ensure_global_config,
    require_config_mode,
)
from ansible_collections.lachlanstone.jetstream.plugins.module_utils.interfaces.interface_builder import (
    build_commands,
)
from ansible_collections.lachlanstone.jetstream.plugins.module_utils.interfaces.interface_classes import (
    _port_id,
    diff_interface,
)
from ansible_collections.lachlanstone.jetstream.plugins.module_utils.interfaces.interface_parsers import (
    get_interface_configuration,
    get_running_config,
)
from ansible_collections.lachlanstone.jetstream.plugins.module_utils.device import (
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
_CONFIG_PROMPT = CONFIG_PROMPT


def _build_change_commands(delta):
    """Build the CLI commands for one interface delta.

    ``build_commands`` only knows how to express ``acceptable_frame_type`` as
    ``tagged``; when the delta asks for ``all`` we insert the ``all`` form
    explicitly before the final ``exit``.
    """
    cmds = build_commands(delta)
    if delta.get("acceptable_frame_type") == "all":
        exit_cmd = cmds.pop() if cmds and cmds[-1] == "exit" else None
        cmds.append("switchport general acceptable-frame-type all")
        if exit_cmd:
            cmds.append(exit_cmd)
    return cmds


def configure_interface(net_connect, iface, config, running, collector, check_mode):
    """Push only the differing settings for one interface to the device.

    Computes the delta between the desired entry and the current state, then
    sends the commands for that delta.  When the interface already matches, no
    command is sent and the step is recorded as unchanged.

    Args:
        net_connect: Active Netmiko connection (already in config mode when
            ``check_mode`` is False).
        iface (dict): One interface entry from ``module.params['interfaces']``.
        config (InterfaceConfig|None): Current state from ``show interface configuration``.
        running (RunningConfigInterface|None): Current state from ``show running-config``.
        collector (ResultCollector): Shared result accumulator.
        check_mode (bool): When True, skip sending; report what would change.
    """
    name = iface["name"]
    settings = {key: value for key, value in iface.items() if key != "name"}

    delta = diff_interface(iface, config, running)

    if delta is None:
        collector.add_step(
            name=f"configure_interface:{name}",
            step_result={
                "changed": False,
                "msg": f"Interface {name}: already in desired state, no changes needed.",
                "commands": [],
                "settings": settings,
                "stdout": "",
            },
        )
        return

    cmds = _build_change_commands(delta)

    if check_mode:
        msg = f"Interface {name}: would apply {len(cmds)} command(s)."
        logger.info(msg)
        collector.add_step(
            name=f"configure_interface:{name}",
            step_result={
                "changed": True,
                "msg": msg,
                "commands": cmds,
                "settings": settings,
                "stdout": "",
            },
        )
        return

    # Recover from a previous block that did not return to global config.
    ensure_global_config(net_connect)

    stdout_parts = []
    for cmd in cmds:
        if cmd == "exit":
            # JetStream does not reprint the prompt after `exit`; don't wait for one.
            output = net_connect.send_command_timing(cmd)
        else:
            output = send_command(
                net_connect,
                cmd,
                expect_string=_CONFIG_PROMPT,
                retries=1,
                mode_aware=True,
            )
        stdout_parts.append(f"# {cmd}\n{output}".strip())
        logger.info("Sent: %s | Output: %s", cmd, output.strip())

        # `interface ...` must actually switch the CLI into interface mode.
        if cmd.startswith("interface "):
            require_config_mode(
                net_connect, "interface", context=f"Interface {name}"
            )

    collector.add_step(
        name=f"configure_interface:{name}",
        step_result={
            "changed": True,
            "msg": f"Interface {name} configured.",
            "commands": cmds,
            "commands_sent": cmds,
            "settings": settings,
            "stdout": "\n".join(stdout_parts),
        },
    )


def run_module(module):
    """Open SSH connection, read current state, and apply only the deltas."""
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

        # Read the current state. ``show`` commands work from config mode too,
        # and entering config mode first keeps the same proven sequence as the
        # original module (enable -> config_mode) instead of desyncing the
        # session with a large ``show running-config`` read beforehand.
        configs = get_interface_configuration(net_connect)
        running_interfaces = get_running_config(net_connect)

        config_by_port = {_port_id(cfg.port): cfg for cfg in configs}
        running_by_port = {rif.name: rif for rif in running_interfaces}

        for iface in interfaces:
            port_id = _port_id(iface["name"])
            configure_interface(
                net_connect,
                iface,
                config_by_port.get(port_id),
                running_by_port.get(port_id),
                collector,
                module.check_mode,
            )

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
            "read_timeout": {"type": "float", "required": False},
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
                        "default": None,
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
