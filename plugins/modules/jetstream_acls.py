#!/usr/bin/python
# -*- coding: utf-8 -*-
# MIT License (see LICENSE)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: jetstream_acls
short_description: Manage access lists on TP-Link JetStream switches
description:
  - Connects to a TP-Link JetStream (Omada) switch over SSH with Netmiko and creates, updates, binds,
    unbinds or removes an access list (ACL) and its rules.
  - Commands are sent through the switch CLI, so the controller running the module needs network access to
    the switch.
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
  state:
    description:
      - V(present) creates the ACL and rules if missing and binds it.
      - V(absent) unbinds and removes the ACL.
      - V(unbind) only unbinds the ACL.
      - V(update) removes and recreates the ACL with the requested rules, then binds it.
    type: str
    choices: [present, absent, unbind, update]
    default: present
  acls:
    description: The access list to manage.
    type: dict
    suboptions:
      id:
        description: ACL number.
        type: str
        required: true
      name:
        description: ACL name.
        type: str
      vid:
        description: VLAN ID the ACL is bound to.
        type: int
      rule_type:
        description: ACL type.
        type: str
        choices: [ip, combined]
      rules:
        description: Ordered list of rules.
        type: list
        elements: dict
        suboptions:
          seq:
            description: Rule sequence number.
            type: int
            required: true
          action:
            description: Rule action.
            type: str
            choices: [permit, deny]
            default: permit
          logging:
            description: Log matches of this rule.
            type: str
            choices: [enable, disable]
            default: disable
          sip:
            description: Source IP address.
            type: str
          sip_mask:
            description: Source IP mask.
            type: str
          dip:
            description: Destination IP address.
            type: str
          dip_mask:
            description: Destination IP mask.
            type: str
          protocol:
            description: IP protocol number.
            type: int
          protocol_name:
            description: IP protocol name.
            type: str
            choices: [ICMP, IGMP, TCP, UDP, IPV6, ESP, AH, OSPF]
          dport:
            description: Destination port.
            type: int
          dport_mask:
            description: Destination port mask.
            type: int
notes:
  - Supports check mode.
"""

EXAMPLES = r"""
- name: Create an ACL that permits printing traffic and bind it
  lachlanstone.jetstream.jetstream_acls:
    host: 192.0.2.10
    username: admin
    password: "{{ vault_switch_password }}"
    enable_password: "{{ vault_switch_enable_password }}"
    state: present
    acls:
      id: "1001"
      name: ALLOW_PRINT
      vid: 10
      rule_type: combined
      rules:
        - seq: 10
          action: permit
          logging: enable
          sip: 10.0.0.0
          sip_mask: 255.255.0.0
          dip: 10.0.0.0
          dip_mask: 255.255.0.0
          protocol_name: TCP
          dport: 9100

- name: Remove an ACL
  lachlanstone.jetstream.jetstream_acls:
    host: 192.0.2.10
    username: admin
    password: "{{ vault_switch_password }}"
    enable_password: "{{ vault_switch_enable_password }}"
    state: absent
    acls:
      id: "1001"
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
  description: Per-step results; more detail is returned at higher Ansible verbosity.
  returned: always
  type: list
  elements: dict
acl_info:
  description: ACL bound and presence state before and after the run.
  returned: when ACL information was collected and verbosity is 2 or higher
  type: dict
"""

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.common import json
from netmiko import ConnectHandler, log
import logging
import time


from plugins.module_utils.send_command import (
    send_command,
)

from plugins.module_utils.acls.acls_parsers import (
    get_current_acls,
    get_bound_access_lists,
    get_protocol_number,
    protocol_names,
)
from plugins.module_utils.acls.acl_classes import (
    ACL,
)

from plugins.module_utils.collector import (
    ResultCollector,
)  # Import the ResultCollector class from the results_collector module
from plugins.module_utils.device import (
    build_device,
)

# NOTE: acl this variable to True will enable console logging for debugging purposes. Set to False to disable console logging.
logging_enabled = True  # Set to True to enable console logging, False to disable

# Component: Configure logging for Netmiko
logger = logging.getLogger(name="netmiko")
logger.setLevel(level=logging.DEBUG)
logger.propagate = False
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
# Component: StreamHandler (logger.info debug messages to console)
# Only attach handlers once; importing this module alongside jetstream_interfaces
# shares the same "netmiko" logger, so guard against duplicate handlers.
if logging_enabled and not logger.handlers:
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level=logging.INFO)
    stream_handler.setFormatter(fmt=formatter)
    logger.addHandler(hdlr=stream_handler)


def unbind_acl(net_connect, collector, module, acl):
    # Component: Set up the command to unbind the ACL and initialize variables for state, check mode, presence, and bound status.
    cmd = f"no access-list bind {acl.id}"
    changed = False
    msg = f"ACL {acl.id} processed."

    if module.params["state"] == "present":
        msg = f"State is 'present', no unbind action required for ACL {acl.id}."
        logger.info(msg)
        collector.add_step(
            name=unbind_acl.__name__,
            step_result={
                "changed": False,
                "msg": msg,
                "command": cmd,
                "acl_bound": acl.is_bound,
            },
        )
        return None

    if module.params["state"] in ["unbind", "absent", "update"]:
        if module.check_mode:
            msg = (
                f"ACL {acl.id} would be unbound."
                if acl.is_bound
                else f"ACL {acl.id} is currently not bound."
            )
        elif acl.is_bound:
            send_command(net_connect, cmd=cmd)
            changed = True
            msg = f"ACL {acl.id} has been unbound."
        else:
            msg = f"ACL {acl.id} is currently not bound."
    else:
        msg = f"Unexpected state '{module.params['state']}' for ACL {acl.id}."
        logger.critical(msg)
        collector.add_step(
            name=unbind_acl.__name__,
            step_result={
                "changed": False,
                "msg": msg,
                "command": cmd,
                "acl_bound": acl.is_bound,
            },
        )
        result = collector.return_info()
        module.fail_json(**result)
        return None

    logger.info(msg)
    collector.add_step(
        name=unbind_acl.__name__,
        step_result={
            "changed": changed,
            "msg": msg,
            "command": cmd,
            "acl_bound": False,
        },
    )
    if module.params["state"] == "unbind":
        result = collector.return_info()
        module.exit_json(**result)
    return None


def remove_acl(net_connect, collector, module, acl, current_acls):
    # Component: Set up the command to remove the ACL and initialize variables for state, check mode, presence, and bound status.
    cmd = f"no access-list create {acl.id}"
    changed = False
    new_acls = current_acls
    msg = f"ACL {acl.id} processed."

    if module.params["state"] == "present":
        msg = f"State is 'present', no removal action required for ACL {acl.id}."
        logger.info(msg)
        collector.add_step(
            name=remove_acl.__name__,
            step_result={
                "changed": False,
                "msg": msg,
                "command": cmd,
                "acl_present": acl.is_present,
                "acl_bound": acl.is_bound,
            },
        )
        return current_acls

    if module.params["state"] in ["absent", "update"]:
        if module.check_mode:
            msg = (
                f"ACL {acl.id} would be removed."
                if acl.is_present
                else f"ACL {acl.id} is currently not present."
            )
        elif acl.is_present:
            send_command(net_connect, cmd=cmd)
            changed = True
            msg = f"ACL {acl.id} has been removed."
            if isinstance(current_acls, dict):
                new_acls = {
                    k: v for k, v in current_acls.items() if str(k) != str(acl.id)
                }
        else:
            msg = f"ACL {acl.id} is currently not present."
    else:
        msg = f"Unexpected state '{module.params['state']}' for ACL {acl.id}."
        logger.critical(msg)
        collector.add_step(
            name=remove_acl.__name__,
            step_result={
                "changed": False,
                "msg": msg,
                "command": cmd,
                "acl_present": acl.is_present,
                "acl_bound": False,
            },
        )
        result = collector.return_info()
        module.fail_json(**result)
        return None

    logger.info(msg)
    if module.params["state"] == "absent":
        collector.add_step(
            name=remove_acl.__name__,
            step_result={
                "changed": changed,
                "msg": msg,
                "command": cmd,
                "acl_present": False,
                "acl_bound": False,
            },
        )
        result = collector.return_info()
        module.exit_json(**result)
    else:
        collector.add_step(
            name=remove_acl.__name__,
            step_result={
                "changed": changed,
                "msg": msg,
                "command": cmd,
                "acl_present": False,
                "acl_bound": False,
            },
        )
        return new_acls


def create_and_update_acl(net_connect, collector, module, acl, current_acls):
    cmd = f"access-list create {acl.id}"
    if acl.name:
        cmd += f' name "{acl.name}"'
    changed = False
    new_acls = current_acls

    if acl.id in current_acls:
        if module.params["state"] == "present":
            msg = f"ACL {acl.id} is present."
            logger.info(msg)
            collector.add_step(
                name=create_and_update_acl.__name__,
                step_result={
                    "changed": False,
                    "msg": msg,
                    "command": cmd,
                    "acl_present": True,
                    "acl_bound": acl.is_bound,
                },
            )
            return current_acls
        elif module.params["state"] == "update":
            msg = f"ACL {acl.id} should not be present on the system when updating. This may indicate a logic error."
        logger.critical(msg)
        collector.add_step(
            name=create_and_update_acl.__name__,
            step_result={
                "changed": False,
                "msg": msg,
                "command": cmd,
                "acl_present": True,
                "acl_bound": acl.is_bound,
            },
        )
        result = collector.return_info()
        module.fail_json(**result)
    elif acl.id not in current_acls:
        if module.params["state"] in ["present", "update"]:
            if module.check_mode:
                msg = f"ACL {acl.id} would be created."
            else:
                send_command(net_connect, cmd=cmd)
                changed = True
                msg = f"ACL {acl.id} has been created."
                if isinstance(current_acls, dict):
                    new_acls = {
                        **current_acls,
                        str(acl.id): {
                            "id": acl.id,
                            "name": acl.name,
                            "type": acl.rule_type,
                            "rules": {},
                        },
                    }
            logger.info(msg)
            collector.add_step(
                name=create_and_update_acl.__name__,
                step_result={
                    "changed": changed,
                    "msg": msg,
                    "command": cmd,
                    "acl_present": True,
                    "acl_bound": False,
                },
            )
            return new_acls


def create_and_update_acl_rules(net_connect, collector, module, acl, current_acls):
    logger.info(f"Creating and updating rules for ACL {acl.id}...")
    if not acl.rules:
        msg = f"No rules provided for ACL {acl.id}. Skipping rule configuration."
        logger.info(msg)
        collector.add_step(
            name=create_and_update_acl_rules.__name__,
            step_result={
                "changed": False,
                "msg": msg,
                "command": "",
                "acl_present": True,
                "acl_bound": acl.is_bound,
            },
        )
        return current_acls
    elif acl.rules:
        rule_commands_ran_list = []
        for rule in acl.rules:
            logger.info(f"Processing rule {rule.seq} for ACL {acl.id}...")
            seq = rule.seq
            action = rule.action
            cmd = f"access-list {acl.rule_type} {acl.id} rule {seq} {action}"
            if rule.logging:
                cmd += " logging enable"
            else:
                cmd += " logging disable"
            if acl.vid and acl.rule_type == "combined":
                cmd += f" vid {acl.vid}"
            if rule.sip and rule.sip_mask:
                cmd += f" sip {rule.sip} sip-mask {rule.sip_mask}"
            if rule.dip and rule.dip_mask:
                cmd += f" dip {rule.dip} dip-mask {rule.dip_mask}"
            protocol_number = None
            if rule.protocol:
                protocol_number = rule.protocol
                cmd += f" protocol {protocol_number}"
            if rule.protocol_name:
                # Convert the Protocol Name to its corresponding protocol number using the get_protocol_number function
                protocol_number = get_protocol_number(rule.protocol_name)
                cmd += f" protocol {protocol_number}"
            if rule.dport and protocol_number in [
                6,
                17,
            ]:  # Only add dport if protocol is TCP (6) or UDP (17)
                if rule.dport_mask is None:
                    rule.dport_mask = (
                        "0000"  # Default value if dport_mask is not provided
                    )
                cmd += f" d-port {rule.dport} d-port-mask {rule.dport_mask}"

            logger.info(f"Processing rule {seq} for ACL {acl.id}...")
            logger.info(f"Sending command: {cmd}")

            if not module.check_mode:
                send_command(net_connect, cmd=cmd)
                rule_commands_ran_list.append(cmd)
                logger.info(f"Rule {seq} for ACL {acl.id} has been configured.")
                time.sleep(5)
            else:
                rule_commands_ran_list.append(cmd)
                logger.info(f"Rule {seq} for ACL {acl.id} would be configured.")

        changed = False if module.check_mode else True
        msg = (
            f"Rules for ACL {acl.id} have been configured."
            if not module.check_mode
            else f"Rules for ACL {acl.id} would be configured."
        )
        collector.add_step(
            name=create_and_update_acl_rules.__name__,
            step_result={
                "changed": changed,
                "msg": msg,
                "command": "; ".join(rule_commands_ran_list),
                "acl_present": True,
                "acl_bound": acl.is_bound,
            },
        )
        return current_acls
    else:
        msg = (
            f"Unexpected condition encountered while processing rules for ACL {acl.id}."
        )
        logger.critical(msg)
        collector.add_step(
            name=create_and_update_acl_rules.__name__,
            step_result={
                "changed": False,
                "msg": msg,
                "command": "",
                "acl_present": True,
                "acl_bound": acl.is_bound,
            },
        )
        result = collector.return_info()
        module.fail_json(**result)


def bind_acls(net_connect, collector, module, acl):
    cmd = f"access-list bind {acl.id}"
    is_changed = False
    if acl.is_bound:
        msg = f"ACL {acl.id} is already bound."
        logger.info(msg)
    else:
        if module.check_mode:
            msg = f"ACL {acl.id} would be bound."
        else:
            send_command(net_connect, cmd=cmd)
            is_changed = True
            msg = f"ACL {acl.id} has been bound."
        logger.info(msg)

    collector.add_step(
        name=bind_acls.__name__,
        step_result={
            "changed": is_changed,
            "msg": msg,
            "command": cmd,
            "acl_present": True,
            "acl_bound": True,
        },
    )
    return collector.return_info()


def run_modules(module):
    logger.info(f"State set = {module.params['state']}")
    device = build_device(module)
    requested_acls = module.params.get("acls") or []
    with ConnectHandler(**device) as net_connect:
        config = net_connect.config_mode()
        logger.info(f"Entered configuration mode: {config}")
        bound_acls = get_bound_access_lists(net_connect)
        current_acls = get_current_acls(net_connect)

        acl: ACL = ACL.from_dict(
            acl=requested_acls, bound_acls=bound_acls, current_acls=current_acls
        )
        collector = ResultCollector()  # Initialize the ResultCollector
        collector.set_basic_info(
            switch=module.params["host"],
            check_mode=module.check_mode,
            verbosity=module._verbosity,
        )
        collector.set_acl_info(
            acl_id=acl.id,
            starting_bind=acl.is_bound,
            finished_bind=None,
            starting_acls=acl.is_present,
            finished_acls=None,
        )

        # Module: Unbind the ACL if it is currently bound and the state is set to 'unbind', 'absent', or 'update'
        unbind_acl(
            net_connect, collector, module, acl
        )  # function: Unbinds the ACL from the device if it is currently bound

        # Module: Remove the ACL if it is currently present and the state is set to 'absent' or 'update'
        new_acls = remove_acl(
            net_connect, collector, module, acl, current_acls
        )  # function: Removes the ACL from the device if it is currently present and the state is set to 'absent' or 'update'
        collector.set_acl_info(
            acl_id=acl.id,
            starting_bind=acl.is_bound,
            finished_bind=None,
            starting_acls=acl.is_present,
            finished_acls=None,
        )
        logger.info(f"New ACLs after removal: {new_acls}")

        # Module: Create or update the ACL if it is not currently present and the state is set to 'present' or 'update'
        new_acls = create_and_update_acl(
            net_connect, collector, module, acl, current_acls=new_acls
        )  # function: Creates and updates the ACL on the device if it is not currently present and the state is set to 'present' or 'update'

        logger.info(f"Requested ACLs: {requested_acls}")
        # Module Define Rules
        new_acls = create_and_update_acl_rules(
            net_connect, collector, module, acl, current_acls=new_acls
        )  # function: Creates and updates the ACL rules on the device if it is not currently present and the state is set to 'present' or 'update'

        # Module: Bind the ACL if it is not currently bound and the state is set to 'present' or 'update'
        bind_acls(
            net_connect, collector, module, acl
        )  # function: Binds the ACL to the device if it is not currently bound and the state is set to 'present' or 'update'

        result = collector.return_info()
        logger.info(f"Final Result: {result}")
        return result


def main():
    module = AnsibleModule(
        argument_spec={
            "host": {"type": "str", "required": True},
            "port": {"type": "int", "default": 22},
            "username": {"type": "str", "required": True},
            "password": {"type": "str", "no_log": True, "default": ""},
            "enable_password": {"type": "str", "no_log": True, "default": ""},
            "state": {
                "type": "str",
                "choices": ["present", "absent", "unbind", "update"],
                "default": "present",
            },
            "acls": {
                "type": "dict",
                "required": False,
                "options": {
                    "id": {"type": "str", "required": True},
                    "name": {"type": "str", "required": False},
                    "vid": {"type": "int", "required": False},
                    "rule_type": {
                        "type": "str",
                        "choices": ["ip", "combined"],
                        "required": False,
                    },
                    "rules": {
                        "type": "list",
                        "elements": "dict",
                        "required": False,
                        "options": {
                            "seq": {"type": "int", "required": True},
                            "action": {
                                "type": "str",
                                "choices": ["permit", "deny"],
                                "default": "permit",
                            },
                            "logging": {
                                "type": "str",
                                "choices": ["enable", "disable"],
                                "default": "disable",
                            },
                            "sip": {"type": "str", "required": False},
                            "sip_mask": {"type": "str", "required": False},
                            "dip": {"type": "str", "required": False},
                            "dip_mask": {"type": "str", "required": False},
                            "protocol": {"type": "int", "required": False},
                            "protocol_name": {
                                "type": "str",
                                "choices": protocol_names(),
                                "required": False,
                            },
                            "dport": {"type": "int", "required": False},
                            "dport_mask": {"type": "int", "required": False},
                        },
                    },
                },
            },
        },
        mutually_exclusive=[["protocol", "protocol_name"]],
        supports_check_mode=True,
    )
    try:
        results = run_modules(module)
        logger.info(f"Results: {results}")
        module.exit_json(**results)
    except Exception as e:
        module.fail_json(msg=str(e))


if __name__ == "__main__":
    main()
