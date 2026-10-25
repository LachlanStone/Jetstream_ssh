"""In-memory models for Omada access lists and their rules."""

from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ACLRule:
    """
    SubModule for storing the details of a single ACL rule, this is utilized by the ACL Class to store all the rules in a list for a given ACL.

    Attributes:
        seq: Rule sequence number.
        action: ``permit`` or ``deny``.
        logging: Whether the device logs matches for this rule.
        sip / sip_mask: Source IP and wildcard mask.
        dip / dip_mask: Destination IP and wildcard mask.
        protocol_name: Named protocol (TCP, UDP, …).
        protocol: Numeric IP protocol.
        dport / dport_mask: Destination port and mask.
    """

    def __init__(
        self,
        seq,
        action,
        logging=False,
        sip=None,
        sip_mask=None,
        dip=None,
        dip_mask=None,
        protocol_name=None,
        protocol=None,
        dport=None,
        dport_mask=None,
    ):
        self.seq = seq
        self.action = action
        self.logging = logging
        self.sip: str = sip
        self.sip_mask = sip_mask
        self.dip = dip
        self.dip_mask = dip_mask
        self.protocol_name = protocol_name
        self.protocol = protocol
        self.dport = dport
        self.dport_mask = dport_mask

    @classmethod
    def from_dict(cls, acl: dict, bound_acls: list):
        """Build a rule from a playbook/module dict. ``logging`` defaults to False; ``dport_mask`` to ``0000``."""
        return cls(
            seq=acl.get("seq"),
            action=acl.get("action"),
            logging=acl.get("logging", False),
            sip=acl.get("sip"),
            sip_mask=acl.get("sip_mask"),
            dip=acl.get("dip"),
            dip_mask=acl.get("dip_mask"),
            protocol_name=acl.get("protocol_name"),
            protocol=acl.get("protocol"),
            dport=acl.get("dport"),
            dport_mask=acl.get("dport_mask", "0000"),
        )


@dataclass
class ACL:
    """
    Store the state of a single ACL parsed from the ansible.module.params, acl_bindings, and current_acls.
    This is utilized to store the inital state of the ACLs, and how the access list will be configured

    Attributes:
        id: ACL identifier on the switch.
        name: ACL name.
        vid: VLAN id this ACL applies to, if any.
        rule_type: ACL type (for example IP or combined).
        state: Desired module state (present, absent, …).
        is_bound: True if this ACL is currently bound on the device.
        is_present: True if this ACL currently exists on the device.
        rules: List of :class:`ACLRule`.
    """

    def __init__(
        self,
        id,
        name,
        vid,
        rule_type,
        state=None,
        is_bound=False,
        is_present=False,
        rules=None,
    ):
        self.id = id
        self.name = name
        self.vid = vid
        self.rule_type = rule_type
        self.state = state
        self.is_bound = is_bound
        self.is_present = is_present
        self.rules = rules if rules is not None else []

    @classmethod
    def from_dict(cls, acl: dict, bound_acls: list, current_acls: list):
        """Build an ACL from a playbook/module dict.

        Sets ``is_bound`` / ``is_present`` from *bound_acls* and *current_acls*
        (membership is by ACL id). Nested rules are converted with
        :meth:`ACLRule.from_dict`.
        """
        return cls(
            id=acl.get("id"),
            name=acl.get("name"),
            vid=acl.get("vid"),
            rule_type=acl.get("rule_type"),
            state=acl.get("state"),
            is_bound=acl.get("id") in bound_acls,
            is_present=acl.get("id") in current_acls,
            rules=[
                ACLRule.from_dict(rule, bound_acls)
                for rule in (acl.get("rules") or [])
            ],
        )


@dataclass
class ReturnResults:
    """Result of a single CLI action.

    Attributes:
        changed: Whether the device configuration changed.
        command: Command that was (or would be) sent.
    """

    def __init__(self, changed: bool, command: str):
        self.changed = changed
        self.command = command
