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


if __name__ == "__main__":
    unittest.main()
