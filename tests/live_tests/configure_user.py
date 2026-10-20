import argparse
import json
import logging
import os
import sys

import _bootstrap  # noqa: F401  puts repo root on sys.path

from plugins.modules.jetstream_user import run_module as _ansible_run_modules


def build_parser():
    parser = argparse.ArgumentParser(description="Live test for jetstream_user")
    parser.add_argument("--host", default=os.environ.get("JETSTREAM_HOST", "192.0.2.10"), help="Switch IP or hostname")
    parser.add_argument("--username", default=os.environ.get("JETSTREAM_USERNAME", "admin"), help="SSH username")
    parser.add_argument("--password", default=os.environ.get("JETSTREAM_PASSWORD", "password"), help="SSH password")
    parser.add_argument("--enable-password", default=os.environ.get("JETSTREAM_ENABLE_PASSWORD", "password"), help="Enable password")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging to the terminal")
    return parser


from fake_module import FakeModule


def run_module_with_params(params):
    fake_module = FakeModule(params)
    try:
        _ansible_run_modules(fake_module)
    except SystemExit:
        pass
    return fake_module._last_exit or {}


if __name__ == "__main__":
    args = build_parser().parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        netmiko_logger = logging.getLogger("netmiko")
        netmiko_logger.setLevel(logging.DEBUG)
        netmiko_logger.propagate = True

    params = {
        "host": args.host,
        "port": 22,
        "username": args.username,
        "password": args.password,
        "enable_password": args.enable_password,
        "name": "test_operator",
        "privilege": "operator",
        "password_type": "secret",
        "encryption_type": 0,
        "user_password": "TestPassword123!",
        "state": "present",
        "save_config": False,
    }

    try:
        results = run_module_with_params(params)
        print(json.dumps(results, indent=2))
    except RuntimeError as e:
        print(json.dumps({"failed": True, "msg": str(e)}, indent=2))
        sys.exit(1)
