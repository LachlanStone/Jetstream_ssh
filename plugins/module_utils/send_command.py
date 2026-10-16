"""Send a CLI command over an existing Netmiko session."""

import re


def send_command(net_connect, cmd, expect_string=None):
    """Run *cmd* and return stripped device output.

    Waits for the current prompt. Retries up to three times when the
    device returns empty output (output sometimes arrives after Netmiko
    has already read).

    Args:
        net_connect: Active Netmiko connection.
        cmd (str): Command to send.
        expect_string (str): Regex of the prompt to wait for. Defaults to the
            current prompt; pass it when the command changes the prompt
            (e.g. entering ``interface ...`` sub-mode).

    Returns:
        str: Command output with prompt and command echo stripped.
    """
    escape_prompt = expect_string or re.escape(net_connect.find_prompt())
    for attempt in range(3):
        output = net_connect.send_command(
            cmd,
            delay_factor=2.0,
            read_timeout=30,
            strip_prompt=True,
            strip_command=True,
            expect_string=escape_prompt
        )
        if output.strip() or attempt == 2:
            break
    return output
