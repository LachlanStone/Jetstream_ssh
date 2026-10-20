import argparse
import json
import logging
import os
import sys

import _bootstrap  # noqa: F401  registers ansible_collections.* -> ./plugins

from ansible_collections.lachlanstone.jetstream.plugins.modules.jetstream_system import (
    run_module as _ansible_run_modules,
)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Live test for jetstream_system covering system info, DNS, NTP, and LLDP."
    )
    # Connection arguments
    parser.add_argument(
        "--host",
        default=os.environ.get("JETSTREAM_HOST", "192.0.2.10"),
        help="Switch IP or hostname",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("JETSTREAM_PORT", "22")),
        help="SSH port",
    )
    parser.add_argument(
        "--username",
        default=os.environ.get("JETSTREAM_USERNAME", "admin"),
        help="SSH username",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("JETSTREAM_PASSWORD", "password"),
        help="SSH password",
    )
    parser.add_argument(
        "--enable-password",
        default=os.environ.get("JETSTREAM_ENABLE_PASSWORD", "password"),
        help="Enable password",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging to the terminal",
    )
    parser.add_argument(
        "--check-mode",
        action="store_true",
        help="Simulate changes without modifying device state",
    )

    # System parameters
    parser.add_argument("--hostname", default="switch-01", help="Switch hostname")
    parser.add_argument("--location", default="Server Room", help="Switch location")
    parser.add_argument("--contact", default="admin@example.com", help="Switch contact")

    # DNS parameters
    parser.add_argument("--dns-primary", default="192.0.2.53", help="Primary DNS server")
    parser.add_argument("--dns-secondary", default="198.51.100.53", help="Secondary DNS server")
    parser.add_argument(
        "--no-dns",
        action="store_true",
        help="Omit DNS configuration from test params",
    )

    # NTP parameters
    parser.add_argument("--ntp-type", default="ntp", help="NTP mode (must be 'ntp' to apply)")
    parser.add_argument("--ntp-utc", default="+00:00", help="NTP UTC offset")
    parser.add_argument(
        "--ntp-servers",
        nargs="+",
        default=["192.0.2.123", "198.51.100.123"],
        help="NTP server addresses (minimum 2 required)",
    )
    parser.add_argument(
        "--ntp-fetch-time",
        type=int,
        default=60,
        help="NTP fetch interval in minutes",
    )
    parser.add_argument(
        "--no-ntp",
        action="store_true",
        help="Omit NTP configuration from test params",
    )

    # LLDP parameters
    parser.add_argument(
        "--lldp",
        dest="lldp_enabled",
        action="store_true",
        default=True,
        help="Enable global LLDP on the switch (default: true)",
    )
    parser.add_argument(
        "--no-lldp",
        dest="lldp_enabled",
        action="store_false",
        help="Disable global LLDP on the switch",
    )
    parser.add_argument(
        "--omit-lldp",
        action="store_true",
        help="Omit LLDP configuration block from test params",
    )

    return parser


from fake_module import FakeModule


def run_module_with_params(params, check_mode=False):
    """Run the Ansible module logic with a plain params dict.

    Returns the result dictionary.
    """
    fake_module = FakeModule(params, check_mode=check_mode)
    try:
        _ansible_run_modules(fake_module)
    except SystemExit as exc:
        if exc.code in (None, 0):
            return fake_module._last_exit or {}
        raise
    return fake_module._last_exit or {}


if __name__ == "__main__":
    args = build_parser().parse_args()

    if args.verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            stream=sys.stdout,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        netmiko_logger = logging.getLogger("netmiko")
        netmiko_logger.setLevel(logging.DEBUG)
        netmiko_logger.propagate = True

    params = {
        "host": args.host,
        "port": args.port,
        "username": args.username,
        "password": args.password,
        "enable_password": args.enable_password,
        "system": {
            "hostname": args.hostname,
            "location": args.location,
            "contact": args.contact,
        },
    }

    if not args.no_dns:
        params["dns"] = {
            "primary": args.dns_primary,
            "secondary": args.dns_secondary,
        }

    if not args.no_ntp:
        params["ntp"] = {
            "type": args.ntp_type,
            "ntp_utc": args.ntp_utc,
            "ntp_servers": args.ntp_servers,
            "ntp_fetch_time": args.ntp_fetch_time,
        }

    if not args.omit_lldp:
        params["lldp"] = {
            "enabled": args.lldp_enabled,
        }

    # Run the module
    try:
        results = run_module_with_params(params, check_mode=args.check_mode)
        print(json.dumps(results, indent=2))
    except RuntimeError as e:
        print(json.dumps({"failed": True, "msg": str(e)}, indent=2))
        sys.exit(1)
