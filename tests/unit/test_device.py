import os
import unittest
import unittest.mock as mock

from plugins.module_utils.device import (
    DEFAULT_READ_TIMEOUT,
    build_device,
    read_timeout_override,
)


class TestReadTimeoutOverride(unittest.TestCase):
    def test_defaults_when_env_is_unset(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(read_timeout_override(), DEFAULT_READ_TIMEOUT)

    def test_env_overrides_default(self):
        with mock.patch.dict(os.environ, {"JETSTREAM_READ_TIMEOUT": "120.5"}):
            self.assertEqual(read_timeout_override(), 120.5)

    def test_invalid_env_raises(self):
        with mock.patch.dict(os.environ, {"JETSTREAM_READ_TIMEOUT": "soon"}):
            with self.assertRaises(ValueError):
                read_timeout_override()

    def test_non_positive_env_raises(self):
        with mock.patch.dict(os.environ, {"JETSTREAM_READ_TIMEOUT": "0"}):
            with self.assertRaises(ValueError):
                read_timeout_override()


class TestBuildDevice(unittest.TestCase):
    def test_includes_read_timeout_override(self):
        params = {
            "host": "192.0.2.10",
            "port": 22,
            "username": "admin",
            "password": "pwd",
            "enable_password": "secret",
        }
        with mock.patch.dict(os.environ, {"JETSTREAM_READ_TIMEOUT": "45"}):
            device = build_device(params)

        self.assertEqual(device["read_timeout_override"], 45.0)
        self.assertEqual(device["host"], "192.0.2.10")

    def test_accepts_an_ansible_module(self):
        module = mock.MagicMock()
        module.params = {
            "host": "192.0.2.10",
            "port": 22,
            "username": "admin",
            "password": "pwd",
            "enable_password": "secret",
        }
        with mock.patch.dict(os.environ, {}, clear=True):
            device = build_device(module)

        self.assertEqual(device["read_timeout_override"], DEFAULT_READ_TIMEOUT)


if __name__ == "__main__":
    unittest.main()
