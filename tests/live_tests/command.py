import argparse
import json
import logging
import os
import sys

import _bootstrap  # noqa: F401  puts repo root on sys.path

from plugins.modules.jetstream_command import (
    send_commands,
)


def build_parser():
    parser = argparse.ArgumentParser(description="Live test for jetstream_command")

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
        "--command-level",
        default="enable",
        choices=["cli", "enable", "config"],
        help="CLI execution level (cli, enable, config)",
    )
    parser.add_argument(
        "--commands",
        nargs="+",
        default=["show system-info"],
        help="CLI commands to execute on the switch",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging to the terminal",
    )
    return parser


def run_commands(params):
    return send_commands(params)


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
        "command_level": args.command_level,
        "command": None,
        "commands": args.commands,
    }

    try:
        results = run_commands(params)
        print(json.dumps(results, indent=2))
    except Exception as e:
        print(json.dumps({"failed": True, "msg": str(e)}, indent=2))
        sys.exit(1)
