import logging
import os
import unittest
from unittest import mock

from plugins.module_utils.logging import (
    DEFAULT_FORMAT,
    LOGGING_ENV_VAR,
    get_logger,
)


class TestGetLogger(unittest.TestCase):
    def setUp(self):
        # Use isolated logger name to avoid interfering with netmiko logger in test suite
        self.test_logger_name = "test_jetstream_logger"
        self._cleanup_logger(self.test_logger_name)

    def tearDown(self):
        self._cleanup_logger(self.test_logger_name)

    def _cleanup_logger(self, name):
        log = logging.getLogger(name)
        for h in list(log.handlers):
            log.removeHandler(h)
        log.handlers.clear()

    def test_default_logger_configuration(self):
        log = get_logger(name=self.test_logger_name)
        self.assertEqual(log.level, logging.DEBUG)
        self.assertFalse(log.propagate)
        self.assertEqual(len(log.handlers), 1)
        handler = log.handlers[0]
        self.assertIsInstance(handler, logging.StreamHandler)
        self.assertEqual(handler.level, logging.INFO)

    def test_idempotent_handler_registration(self):
        log1 = get_logger(name=self.test_logger_name)
        self.assertEqual(len(log1.handlers), 1)

        # Calling again must not duplicate handlers
        log2 = get_logger(name=self.test_logger_name)
        self.assertIs(log1, log2)
        self.assertEqual(len(log2.handlers), 1)

    def test_disabled_explicitly(self):
        log = get_logger(name=self.test_logger_name, enabled=False)
        self.assertEqual(len(log.handlers), 0)

    def test_disabled_via_env_var(self):
        for disable_val in ("0", "false", "no", "off", "FALSE"):
            with mock.patch.dict(os.environ, {LOGGING_ENV_VAR: disable_val}):
                self._cleanup_logger(self.test_logger_name)
                log = get_logger(name=self.test_logger_name)
                self.assertEqual(len(log.handlers), 0)

    def test_enabled_via_env_var(self):
        with mock.patch.dict(os.environ, {LOGGING_ENV_VAR: "1"}):
            log = get_logger(name=self.test_logger_name)
            self.assertEqual(len(log.handlers), 1)
