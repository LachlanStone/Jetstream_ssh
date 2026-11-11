#!/usr/bin/python
# -*- coding: utf-8 -*-
# MIT License (see LICENSE)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.module_utils.basic import AnsibleModule
from netmiko import ConnectHandler
from netmiko.utilities import structured_data_converter
from ansible_collections.lachlanstone.jetstream.plugins.module_utils.device import (
    build_device,
)
from ansible_collections.lachlanstone.jetstream.plugins.module_utils.logging import (
    logger,
)
from ansible_collections.lachlanstone.jetstream.plugins.module_utils.connection import (
    CONNECTION_ARGS,
    CONNECTION_DOCUMENTATION,
)

DOCUMENTATION = r"""
---
module: jetstream_command
short_description: Run CLI commands on TP-Link JetStream switches
description:
  - Connects to a TP-Link JetStream (Omada) switch over SSH with Netmiko and runs one or more CLI commands.
  - Returns the raw output, the output split into lines, a simple key and value parse, and the TextFSM parse
    when a matching template is available.
  - To use the bundled TextFSM template, set the C(NET_TEXTFSM) environment variable to the path of
    C(extras/ntc_templates) inside the installed collection.
version_added: "0.1.0"
author:
  - Lachlan Stone (@lachlanstone)
requirements:
  - netmiko
options:
""" + CONNECTION_DOCUMENTATION + r"""
  command_level:
    description:
      - CLI mode to run the commands in.
      - V(cli) uses user mode, V(enable) enters privileged mode, V(config) enters privileged and then global configuration mode.
    type: str
    choices: [cli, enable, config]
    default: cli
  command:
    description: A single command to run. Ignored when O(commands) is set.
    type: str
  commands:
    description: List of commands to run. When neither O(command) nor O(commands) is set, V(show system-info) runs.
    type: list
    elements: str
notes:
  - Does not support check mode; it exits without running commands in check mode.
"""

EXAMPLES = r"""
- name: Show system information and VLANs
  lachlanstone.jetstream.jetstream_command:
    host: 192.0.2.10
    username: admin
    password: "{{ vault_switch_password }}"
    enable_password: "{{ vault_switch_enable_password }}"
    command_level: enable
    commands:
      - show system-info
      - show vlan
  register: switch_result
"""

RETURN = r"""
commands:
  description: One entry per command that was run.
  returned: success
  type: list
  elements: dict
  contains:
    command:
      description: The command that was run.
      type: str
    stdout:
      description: Raw command output.
      type: str
    stdout_lines:
      description: Non-empty output lines.
      type: list
      elements: str
    textfsm_parsed:
      description: TextFSM parse result, or the raw output string when no template matched.
      type: raw
    parsed:
      description: Key and value pairs parsed from lines of the form C(key - value).
      type: dict
      returned: when at least one line matched
"""


def parse_output(output):
    parsed = {}
    for line in output.splitlines():
        if " - " in line:
            k, v = line.split(" - ", 1)
            parsed[k.strip()] = v.strip()
    return parsed


def send_commands(params):
    device = build_device(params)
    cmds = params["commands"] or ([params["command"]] if params.get("command") else ["show system-info"])

    with ConnectHandler(**device) as net_connect:
        if params["command_level"] in ["enable", "config"]:
            net_connect.enable()
        if params["command_level"] == "config":
            net_connect.config_mode()
        results = []
        for cmd in cmds:
            raw = net_connect.send_command(cmd, auto_find_prompt=True)
            textfsm_parsed = structured_data_converter(
                raw_data=raw,
                command=cmd,
                platform=net_connect.device_type,
                use_textfsm=True,
            )
            lines = [line.strip() for line in raw.splitlines() if line.strip()]
            item = {"command": cmd, "stdout": raw, "stdout_lines": lines, "textfsm_parsed": textfsm_parsed}
            parsed = parse_output(raw)
            if parsed:
                item["parsed"] = parsed
            results.append(item)
        return results


def main():
    argument_spec = {}
    argument_spec.update(CONNECTION_ARGS)
    argument_spec.update(
        {
            "command_level": {"type": "str", "choices": ["cli", "enable", "config"], "default": "cli"},
            "command": {"type": "str", "required": False},
            "commands": {"type": "list", "elements": "str", "required": False},
        }
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
    )

    try:
        results = send_commands(module.params)
        module.exit_json(changed=False, commands=results)
    except Exception as e:
        module.fail_json(msg=str(e))


if __name__ == "__main__":
    main()
