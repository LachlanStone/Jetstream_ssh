import unittest
import unittest.mock as mock

from netmiko.exceptions import ReadTimeout

from plugins.module_utils.send_command import send_command


class TestSendCommand(unittest.TestCase):
    def test_sends_once_when_output_is_empty(self):
        conn = mock.MagicMock()
        conn.find_prompt.return_value = "switch(config)#"
        conn.send_command.return_value = ""

        output = send_command(conn, "vlan 10", expect_string=r"\(config[^)]*\)#")

        self.assertEqual(output, "")
        self.assertEqual(conn.send_command.call_count, 1)

    def test_sends_once_when_output_is_not_empty(self):
        conn = mock.MagicMock()
        conn.find_prompt.return_value = "switch(config)#"
        conn.send_command.return_value = "some output"

        output = send_command(conn, "show vlan")

        self.assertEqual(output, "some output")
        self.assertEqual(conn.send_command.call_count, 1)

    def test_timeout_is_not_retried(self):
        conn = mock.MagicMock()
        conn.find_prompt.return_value = "switch(config)#"
        conn.send_command.side_effect = ReadTimeout("pattern not detected")

        with self.assertRaises(ReadTimeout):
            send_command(conn, "show vlan")

        self.assertEqual(conn.send_command.call_count, 1)

    def test_timeout_is_retried_when_opted_in(self):
        conn = mock.MagicMock()
        conn.find_prompt.return_value = "switch#"
        conn.send_command.side_effect = [
            ReadTimeout("pattern not detected"),
            "vlan 1",
        ]

        with mock.patch("plugins.module_utils.send_command.time.sleep"):
            output = send_command(conn, "show vlan", retries=1)

        self.assertEqual(output, "vlan 1")
        self.assertEqual(conn.send_command.call_count, 2)
        conn.clear_buffer.assert_called_once_with()

    def test_timeout_raises_after_retries_exhausted(self):
        conn = mock.MagicMock()
        conn.find_prompt.return_value = "switch#"
        conn.send_command.side_effect = ReadTimeout("pattern not detected")

        with mock.patch("plugins.module_utils.send_command.time.sleep"):
            with self.assertRaises(ReadTimeout):
                send_command(conn, "show vlan", retries=2)

        self.assertEqual(conn.send_command.call_count, 3)

    def test_mode_aware_retries_when_prompt_unchanged(self):
        conn = mock.MagicMock()
        conn.find_prompt.side_effect = [
            "switch(config)#",  # before the command
            "switch(config)#",  # after the timeout
        ]
        conn.send_command.side_effect = [
            ReadTimeout("pattern not detected"),
            "",
        ]

        with mock.patch("plugins.module_utils.send_command.time.sleep"):
            output = send_command(
                conn,
                "name Servers",
                expect_string=r"\(config[^)]*\)#",
                retries=1,
                mode_aware=True,
            )

        self.assertEqual(output, "")
        self.assertEqual(conn.send_command.call_count, 2)
        conn.clear_buffer.assert_called_once_with()

    def test_mode_aware_does_not_resend_after_context_change(self):
        conn = mock.MagicMock()
        conn.find_prompt.side_effect = [
            "switch(config)#",      # before the command
            "switch(config-if)#",   # command entered interface mode
        ]
        conn.send_command.side_effect = ReadTimeout("pattern not detected")

        output = send_command(
            conn,
            "interface vlan 10",
            expect_string=r"\(config[^)]*\)#",
            retries=1,
            mode_aware=True,
        )

        self.assertEqual(output, "")
        self.assertEqual(conn.send_command.call_count, 1)
        conn.clear_buffer.assert_called_once_with()

    def test_mode_aware_raises_when_prompt_probe_fails(self):
        conn = mock.MagicMock()
        conn.find_prompt.side_effect = [
            "switch(config)#",
            RuntimeError("probe failed"),
        ]
        conn.send_command.side_effect = ReadTimeout("pattern not detected")

        with self.assertRaises(ReadTimeout):
            send_command(
                conn,
                "interface vlan 10",
                expect_string=r"\(config[^)]*\)#",
                retries=1,
                mode_aware=True,
            )

        self.assertEqual(conn.send_command.call_count, 1)

    def test_mode_aware_refuses_to_retry_without_starting_prompt(self):
        conn = mock.MagicMock()
        conn.find_prompt.return_value = ""
        conn.send_command.side_effect = ReadTimeout("pattern not detected")

        with self.assertRaises(ReadTimeout):
            send_command(
                conn,
                "interface vlan 10",
                expect_string=r"\(config[^)]*\)#",
                retries=1,
                mode_aware=True,
            )

        self.assertEqual(conn.send_command.call_count, 1)


if __name__ == "__main__":
    unittest.main()
