"""In-memory models for TP-Link JetStream physical interface configuration."""

from dataclasses import dataclass, field
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class InterfaceConfig:
    """State of a single physical interface as reported by ``show interface configuration``.

    Attributes:
        port: Port identifier as printed by the switch (e.g. ``Tw1/0/1``, ``Te1/0/25``).
        state: Administrative state string — ``Enable`` or ``Disable``.
        speed: Speed string — ``Auto``, ``10G``, ``1G``, etc.
        duplex: Duplex string — ``Auto``, ``Full``, ``Half``.
        flow_ctrl: Flow control string — ``Enable`` or ``Disable``.
        description: Optional port description; empty string when not set.
        enabled: Convenience bool derived from *state*.
    """

    def __init__(
        self,
        port: str,
        state: str,
        speed: str,
        duplex: str,
        flow_ctrl: str,
        description: str = "",
    ):
        self.port = port
        self.state = state
        self.speed = speed
        self.duplex = duplex
        self.flow_ctrl = flow_ctrl
        self.description = description
        self.enabled: bool = state.strip().lower() == "enable"

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    @classmethod
    def from_parsed_line(cls, fields: list) -> "InterfaceConfig":
        """Build an ``InterfaceConfig`` from a tokenised output line.

        The switch prints between five and six whitespace-separated tokens:

        .. code-block:: text

            Tw1/0/1   Enable   Auto   Auto   Disable
            Tw1/0/1   Enable   Auto   Auto   Disable   Server uplink

        Args:
            fields: List of stripped tokens from one data line.

        Returns:
            :class:`InterfaceConfig`

        Raises:
            ValueError: Fewer than five tokens supplied.
        """
        if len(fields) < 5:
            raise ValueError(
                f"Expected at least 5 fields, got {len(fields)}: {fields!r}"
            )
        description = " ".join(fields[5:]) if len(fields) > 5 else ""
        return cls(
            port=fields[0],
            state=fields[1],
            speed=fields[2],
            duplex=fields[3],
            flow_ctrl=fields[4],
            description=description,
        )

    @classmethod
    def from_dict(cls, data: dict) -> "InterfaceConfig":
        """Build an ``InterfaceConfig`` from a plain dictionary.

        Useful when constructing instances from module params or test fixtures.

        Args:
            data: Dict with keys matching the class attributes.

        Returns:
            :class:`InterfaceConfig`
        """
        return cls(
            port=data["port"],
            state=data.get("state", "Enable"),
            speed=data.get("speed", "Auto"),
            duplex=data.get("duplex", "Auto"),
            flow_ctrl=data.get("flow_ctrl", "Disable"),
            description=data.get("description", ""),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Return a plain-dict representation of this interface."""
        return {
            "port": self.port,
            "state": self.state,
            "speed": self.speed,
            "duplex": self.duplex,
            "flow_ctrl": self.flow_ctrl,
            "description": self.description,
            "enabled": self.enabled,
        }

    def __repr__(self) -> str:
        return (
            f"InterfaceConfig(port={self.port!r}, state={self.state!r}, "
            f"speed={self.speed!r}, duplex={self.duplex!r}, "
            f"flow_ctrl={self.flow_ctrl!r}, description={self.description!r})"
        )


@dataclass
class RunningConfigInterface:
    """State of a single physical interface as reported by ``show running-config``.

    Attributes:
        name: Port identifier as printed by the switch (e.g. ``1/0/1``).
        port_type: Interface type (e.g. ``two-gigabitEthernet``).
        description: Optional port description; empty string when not set.
        pvid: Port VLAN ID; ``None`` when no PVID is set.
        vlans_untagged: VLAN IDs the port carries untagged.
        vlans_tagged: VLAN IDs the port carries tagged.
        vlans_disabled: VLAN IDs removed from the port.
        acceptable_frame_type: ``all`` or ``tagged``.
        flowcontrol: Always ``None``; running-config carries no flow-control state.
    """

    name: str
    port_type: str
    description: str = ""
    pvid: Optional[int] = None
    vlans_untagged: list = field(default_factory=list)
    vlans_tagged: list = field(default_factory=list)
    vlans_disabled: list = field(default_factory=list)
    acceptable_frame_type: str = "all"
    flowcontrol: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "RunningConfigInterface":
        """Build a :class:`RunningConfigInterface` from a plain dictionary."""
        return cls(
            name=data["name"],
            port_type=data["port_type"],
            description=data.get("description", ""),
            pvid=data.get("pvid"),
            vlans_untagged=list(data.get("vlans_untagged", [])),
            vlans_tagged=list(data.get("vlans_tagged", [])),
            vlans_disabled=list(data.get("vlans_disabled", [])),
            acceptable_frame_type=data.get("acceptable_frame_type", "all"),
            flowcontrol=data.get("flowcontrol"),
        )

    def to_dict(self) -> dict:
        """Return a plain-dict representation of this interface."""
        return {
            "name": self.name,
            "port_type": self.port_type,
            "description": self.description,
            "pvid": self.pvid,
            "vlans_untagged": list(self.vlans_untagged),
            "vlans_tagged": list(self.vlans_tagged),
            "vlans_disabled": list(self.vlans_disabled),
            "acceptable_frame_type": self.acceptable_frame_type,
            "flowcontrol": self.flowcontrol,
        }


# ---------------------------------------------------------------------------
# Desired-vs-current comparison (idempotency)
# ---------------------------------------------------------------------------

# Canonical speed values. Module tokens (``1000``, ``auto``) and switch display
# tokens (``1G``, ``Auto``) map to the same canonical value so that a configured
# speed is recognised as already applied.  An unrecognised switch token returns
# ``None`` and is treated as a difference — fail-safe against config drift.
_SPEED_CANONICAL = {
    "auto": "auto",
    "10": 10,
    "10m": 10,
    "100": 100,
    "100m": 100,
    "1000": 1000,
    "1g": 1000,
    "1000m": 1000,
    "2500": 2500,
    "2500m": 2500,
    "2.5g": 2500,
    "10000": 10000,
    "10g": 10000,
    "10000m": 10000,
}

# Fields whose desired value is a list of VLAN IDs compared as unordered sets.
_VLAN_FIELDS = ("vlans_untagged", "vlans_tagged", "vlans_disabled")


def _port_id(token: str) -> str:
    """Return the numeric port identifier for a port token.

    Normalises the three representations the collection sees::

        ``1/0/1``                      -> ``1/0/1``
        ``Tw1/0/1``                    -> ``1/0/1``
        ``two-gigabitEthernet 1/0/1``  -> ``1/0/1``
    """
    value = (token or "").strip()
    if " " in value:
        value = value.split(None, 1)[1].strip()
    return re.sub(r"^[A-Za-z]+", "", value)


def _normalize_speed(value: Optional[str]):
    """Return the canonical speed for *value*, or ``None`` when unrecognised."""
    if value is None:
        return None
    return _SPEED_CANONICAL.get(str(value).strip().lower())


def _current_description(config, running) -> str:
    """Return the authoritative current description.

    ``show running-config`` is preferred; it reflects the configured
    description.  Fall back to ``show interface configuration`` when the
    running-config view is unavailable.
    """
    if running is not None:
        return running.description
    if config is not None:
        return config.description
    return ""


def diff_interface(desired: dict, config=None, running=None):
    """Return the settings that must change for one desired interface.

    Compares an ``interfaces`` entry (Ansible defaults applied) against the
    current state reported by ``show interface configuration``
    (:class:`InterfaceConfig`) and ``show running-config``
    (:class:`RunningConfigInterface`).

    Only settings with an explicit desired value are managed: ``None`` for
    scalar fields and an empty list for VLAN fields mean "leave as-is" and are
    never emitted.  A description of ``""`` explicitly clears the description.

    Args:
        desired: One ``interfaces`` entry from module params.
        config: Matching :class:`InterfaceConfig`, or ``None`` when not found.
        running: Matching :class:`RunningConfigInterface`, or ``None``.

    Returns:
        dict: A delta suitable for :func:`interface_builder.build_commands`
        containing ``name``/``port_type`` plus only the differing settings.
        ``None`` when nothing differs.
    """
    delta = {"name": desired["name"]}
    if desired.get("port_type"):
        delta["port_type"] = desired["port_type"]

    changed = False

    # Administrative state: True -> Enable, False -> Disable.
    enabled = desired.get("enabled")
    if enabled is not None:
        current_enabled = config.enabled if config is not None else None
        if current_enabled != bool(enabled):
            delta["enabled"] = bool(enabled)
            changed = True

    # Speed. ``None`` leaves the port untouched; the switch default is ``Auto``.
    speed = desired.get("speed")
    if speed is not None:
        current_speed = _normalize_speed(config.speed if config is not None else None)
        if _normalize_speed(speed) != current_speed:
            delta["speed"] = speed
            changed = True

    # Description. ``build_commands`` emits "no description" for None and
    # nothing for "", so the delta must always carry this key:
    #   ""    -> leave unchanged (no command)
    #   None  -> clear ("no description")
    #   "..." -> set ("description ...")
    description = desired.get("description")
    if description is None or description == _current_description(config, running):
        delta["description"] = ""
    elif description == "":
        delta["description"] = None
        changed = True
    else:
        delta["description"] = description
        changed = True

    # PVID.
    pvid = desired.get("pvid")
    if pvid is not None:
        current_pvid = running.pvid if running is not None else None
        # A physical port with no ``switchport pvid`` line is on VLAN 1.
        if running is not None and current_pvid is None:
            current_pvid = 1
        if current_pvid != pvid:
            delta["pvid"] = pvid
            changed = True

    # VLAN membership is additive: the requested set must already be present.
    # The builder can only add allowed/removed VLANs, so an equality check
    # would resend the same commands on every run and never converge.
    for key in _VLAN_FIELDS:
        desired_vlans = desired.get(key) or []
        if not desired_vlans:
            continue
        current_vlans = getattr(running, key, []) if running is not None else []
        if not set(desired_vlans).issubset(set(current_vlans)):
            delta[key] = list(desired_vlans)
            changed = True

    # Acceptable frame type. ``all`` is the default but is still a meaningful
    # desired state, so it is always compared.
    acceptable = desired.get("acceptable_frame_type")
    if acceptable is not None:
        current_acceptable = running.acceptable_frame_type if running is not None else None
        if current_acceptable is None:
            current_acceptable = "all"
        if acceptable != current_acceptable:
            delta["acceptable_frame_type"] = acceptable
            changed = True

    if not changed:
        return None
    return delta
