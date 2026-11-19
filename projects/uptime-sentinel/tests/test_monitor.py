import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sentinel.monitor import Result, Target, check, read_targets, save_results, summarize


class TestMonitor(unittest.TestCase):
    def test_reads_valid_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "targets.json"
            path.write_text(json.dumps({"targets": [{"name": "Local", "url": "http://localhost:8080"}]}))
            self.assertEqual(read_targets(path), [Target("Local", "http://localhost:8080")])

    def test_rejects_unsupported_scheme(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "targets.json"
            path.write_text(json.dumps({"targets": [{"name": "Bad", "url": "file:///etc/passwd"}]}))
            with self.assertRaises(ValueError):
                read_targets(path)

    def test_successful_check(self):
        class Response:
            status = 204
            def __enter__(self): return self
            def __exit__(self, *args): pass
        with patch("sentinel.monitor.urlopen", return_value=Response()):
            result = check(Target("service", "https://example.com", 204))
            self.assertTrue(result.ok)
            self.assertEqual(result.status, 204)
            self.assertGreaterEqual(result.latency_ms, 0)

    def test_persists_results_and_uptime(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "history.db"
            results = [Result("api", "https://example.com", "2026-01-01T00:00:00Z", True, 200, 12.0),
                       Result("api", "https://example.com", "2026-01-01T00:01:00Z", False, 500, 20.0)]
            save_results(db, results)
            report = summarize(db)
            self.assertEqual(report[0]["uptime_percent"], 50.0)
            self.assertEqual(report[0]["avg_latency_ms"], 16.0)


if __name__ == "__main__":
    unittest.main()
