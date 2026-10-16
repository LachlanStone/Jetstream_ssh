#!/usr/bin/python
# -*- coding: utf-8 -*-
# MIT License (see LICENSE)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

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

from ansible.module_utils.basic import AnsibleModule
from netmiko import ConnectHandler
import os

def parse_output(output):
    parsed = {}
    for line in output.splitlines():
        if " - " in line:
            k, v = line.split(" - ", 1)
            parsed[k.strip()] = v.strip()
    return parsed


def send_commands(params):
    device = {
        "device_type": "tplink_jetstream",
        "host": params["host"],
        "port": params["port"],
        "username": params["username"],
        "password": params["password"],
        "secret": params["enable_password"],
    }
    cmds = params["commands"] or ([params["command"]] if params.get("command") else ["show system-info"])

    with ConnectHandler(**device) as net_connect:
        if params["command_level"] in ["enable", "config"]:
            net_connect.enable()
        if params["command_level"] == "config":
            net_connect.config_mode()
        results = []
        for cmd in cmds:
            textfsm_parsed = net_connect.send_command(cmd, use_textfsm=True, auto_find_prompt=True)
            raw = net_connect.send_command(cmd)
            lines = [line.strip() for line in raw.splitlines() if line.strip()]
            item = {"command": cmd, "stdout": raw, "stdout_lines": lines, "textfsm_parsed": textfsm_parsed}
            parsed = parse_output(raw)
            if parsed:
                item["parsed"] = parsed
            results.append(item)
        return results


def main():
    module = AnsibleModule(
        argument_spec={
            "host": {"type": "str", "required": True},
            "port": {"type": "int", "default": 22},
            "username": {"type": "str", "required": True},
            "password": {"type": "str", "no_log": True, "default": ""},
            "enable_password": {"type": "str", "no_log": True, "default": ""},
            "command_level": {"type": "str", "choices": ["cli", "enable", "config"], "default": "cli"},
            "command": {"type": "str", "required": False},
            "commands": {"type": "list", "elements": "str", "required": False},
        },
        supports_check_mode=False,
    )

    if module.check_mode:
        module.exit_json(changed=False, msg="Check mode - no commands executed")

    try:
        results = send_commands(module.params)
        module.exit_json(changed=False, commands=results)
    except Exception as e:
        module.fail_json(msg=str(e))


if __name__ == "__main__":
    main()
