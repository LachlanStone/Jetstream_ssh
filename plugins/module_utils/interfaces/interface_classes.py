"""In-memory models for TP-Link JetStream physical interface configuration."""

from dataclasses import dataclass
import logging

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
