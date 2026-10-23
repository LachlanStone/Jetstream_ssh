"""Send a CLI command over an existing Netmiko session."""

import re
import time

from netmiko.exceptions import ReadTimeout


def send_command(
    net_connect,
    cmd,
    expect_string=None,
    retries=0,
    read_timeout=30,
):
    """Run *cmd* and return stripped device output.

    Netmiko already waits for the prompt before returning, so an empty
    result means the command produced no CLI output (normal for config
    commands such as ``vlan 10`` and ``interface vlan 10``). Do not
    resend on empty output: by then the switch may be in a new context,
    and a second send makes the CLI report ``Error: Bad command``.

    On ``ReadTimeout`` the command may or may not have been applied, so
    retries are opt-in via ``retries`` and should only be used for
    read-only/idempotent commands (``show ...``). Before each retry the
    channel is drained so stale output cannot be mistaken for the retry's
    output.

    Args:
        net_connect: Active Netmiko connection.
        cmd (str): Command to send.
        expect_string (str): Regex of the prompt to wait for. Defaults to the
            current prompt; pass it when the command changes the prompt
            (e.g. entering ``interface ...`` sub-mode).
        retries (int): Extra attempts after a ``ReadTimeout``. Defaults to 0.
        read_timeout (int): Seconds to wait for the expected prompt.

    Returns:
        str: Command output with prompt and command echo stripped.
    """

    escape_prompt = expect_string or re.escape(net_connect.find_prompt())
    attempts = max(retries, 0) + 1

    for attempt in range(attempts):
        try:
            return net_connect.send_command(
                cmd,
                delay_factor=2.0,
                read_timeout=read_timeout,
                strip_prompt=True,
                strip_command=True,
                expect_string=escape_prompt,
            )
        except ReadTimeout:
            if attempt == attempts - 1:
                raise
            net_connect.clear_buffer()
            time.sleep(1)
