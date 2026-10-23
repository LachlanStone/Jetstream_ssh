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
    mode_aware=False,
):
    """Run *cmd* and return stripped device output.

    Netmiko already waits for the prompt before returning, so an empty
    result means the command produced no CLI output (normal for config
    commands such as ``vlan 10`` and ``interface vlan 10``). Do not
    resend on empty output: by then the switch may be in a new context,
    and a second send makes the CLI report ``Error: Bad command``.

    On ``ReadTimeout`` the command may or may not have been applied, so
    retries are opt-in via ``retries``.

    With ``mode_aware=True`` the prompt is captured before sending and
    checked again after a timeout:

    - prompt unchanged: the command may not have run, so it is retried;
    - prompt changed: the command changed CLI context, so it is assumed
      to have been applied and is not resent.

    Use ``mode_aware`` for idempotent config commands. Keep
    ``mode_aware=False`` for commands that must never be repeated, such
    as ACL creation or user creation.

    Args:
        net_connect: Active Netmiko connection.
        cmd (str): Command to send.
        expect_string (str): Regex of the prompt to wait for. Defaults to the
            current prompt; pass it when the command changes the prompt
            (e.g. entering ``interface ...`` sub-mode).
        retries (int): Extra attempts after a ``ReadTimeout``. Defaults to 0.
        read_timeout (int): Seconds to wait for the expected prompt.
        mode_aware (bool): Compare prompts across retries. Defaults to False.

    Returns:
        str: Command output with prompt and command echo stripped.
    """

    escape_prompt = expect_string or re.escape(net_connect.find_prompt())
    attempts = max(retries, 0) + 1
    mode_aware_active = attempts > 1 and mode_aware
    start_prompt = None
    if mode_aware_active:
        start_prompt = net_connect.find_prompt().strip()

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
        except ReadTimeout as exc:
            if attempt == attempts - 1:
                raise

            if mode_aware_active:
                if not start_prompt:
                    # Without a known starting mode, resending a config
                    # command could duplicate it in the wrong context.
                    raise
                try:
                    current_prompt = net_connect.find_prompt().strip()
                except Exception:
                    raise exc

                if current_prompt != start_prompt and current_prompt.endswith("#"):
                    # The command advanced the CLI to another context; resending
                    # it there would be invalid.
                    net_connect.clear_buffer()
                    return ""

            net_connect.clear_buffer()
            time.sleep(1)
