import unittest
from plugins.module_utils.collector import ResultCollector


class TestCollector(unittest.TestCase):
    def test_return_info_without_steps(self):
        collector = ResultCollector()
        collector.set_basic_info(switch="192.0.2.1", check_mode=True)
        res = collector.return_info()
        self.assertEqual(res["current_state"], "")
        self.assertFalse(res["changed"])
        self.assertEqual(res["switch"], "192.0.2.1")
        self.assertTrue(res["check_mode"])
        self.assertEqual(res["cmd"], "")
        self.assertEqual(res["steps"], [])
