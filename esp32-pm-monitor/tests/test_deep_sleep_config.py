import importlib.util
import unittest
from pathlib import Path

from fastapi import HTTPException


ROOT = Path(__file__).resolve().parents[1]
APP_PATHS = (ROOT / "app.py", ROOT / "backend" / "app.py")


class FakeCursor:
    def __init__(self, state):
        self.state = state
        self.rows = []

    def execute(self, sql, params=None):
        if sql.startswith("SELECT key, value FROM config"):
            self.rows = [
                (key, self.state[key])
                for key in ("interval_sec", "deep_sleep_enabled")
                if key in self.state
            ]
        elif "VALUES ('interval_sec', %s)" in sql:
            self.state["interval_sec"] = params[0]
        elif "VALUES ('deep_sleep_enabled', %s)" in sql:
            self.state["deep_sleep_enabled"] = params[0]

    def fetchall(self):
        return self.rows

    def close(self):
        pass


class FakeConnection:
    def __init__(self, state):
        self.state = state

    def cursor(self):
        return FakeCursor(self.state)

    def commit(self):
        pass

    def close(self):
        pass


def load_app(path):
    spec = importlib.util.spec_from_file_location(f"test_{path.parent.name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DeepSleepConfigurationTests(unittest.TestCase):
    def assert_rejected_without_mutation(self, path, initial, update):
        module = load_app(path)
        state = initial.copy()
        module.get_db = lambda: FakeConnection(state)

        with self.assertRaises(HTTPException) as error:
            module.put_config(module.ConfigUpdate(**update))

        self.assertEqual(error.exception.status_code, 422)
        self.assertEqual(state, initial)

    def test_cannot_enable_deep_sleep_with_stored_short_interval(self):
        for path in APP_PATHS:
            with self.subTest(app=path):
                self.assert_rejected_without_mutation(
                    path,
                    {"interval_sec": "30", "deep_sleep_enabled": "0"},
                    {"deep_sleep_enabled": True},
                )

    def test_cannot_shorten_interval_while_deep_sleep_is_enabled(self):
        for path in APP_PATHS:
            with self.subTest(app=path):
                self.assert_rejected_without_mutation(
                    path,
                    {"interval_sec": "900", "deep_sleep_enabled": "1"},
                    {"interval_sec": 30},
                )

    def test_can_enable_deep_sleep_and_raise_interval_atomically(self):
        for path in APP_PATHS:
            with self.subTest(app=path):
                module = load_app(path)
                state = {"interval_sec": "30", "deep_sleep_enabled": "0"}
                module.get_db = lambda: FakeConnection(state)

                result = module.put_config(
                    module.ConfigUpdate(interval_sec=900, deep_sleep_enabled=True)
                )

                self.assertEqual(result, {"interval_sec": 900, "deep_sleep_enabled": True})
                self.assertEqual(state, {"interval_sec": "900", "deep_sleep_enabled": "1"})


if __name__ == "__main__":
    unittest.main()
