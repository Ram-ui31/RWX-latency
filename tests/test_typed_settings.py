"""Regression checks for settings provenance and reused-worker ownership."""

import sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.typed_settings.choose import setting
from research.typed_settings import hook


def read_owner():
    from research.typed_settings import hook

    return hook.active


class TypedSettingsTests(unittest.TestCase):
    def test_scalar_setting_requires_one_value_change(self):
        a = "class A:\n    FLAG = True\n    OTHER = 2\n"
        self.assertEqual(setting(a, a.replace("True", "False")), "A.FLAG")
        self.assertIsNone(setting(a, a.replace("True", "False").replace("2", "3")))
        self.assertIsNone(setting(a, a.replace("True", "1")))

    def test_nested_owner_and_executable_change(self):
        a = "class A:\n    class B:\n        FLAG = 1\n    def f(self):\n        return 3\n"
        self.assertEqual(setting(a, a.replace("FLAG = 1", "FLAG = 2")), "A.B.FLAG")
        self.assertIsNone(
            setting(
                a, a.replace("FLAG = 1", "FLAG = 2").replace("return 3", "return 4")
            )
        )

    def test_worker_owner_changes_for_every_task(self):
        import multiprocessing
        from concurrent.futures import ProcessPoolExecutor

        with ProcessPoolExecutor(
            max_workers=1, mp_context=multiprocessing.get_context("spawn")
        ) as pool:
            self.assertEqual(
                pool.submit(hook.task, "first", read_owner, (), {}).result(timeout=10),
                "first",
            )
            self.assertEqual(
                pool.submit(hook.task, "second", read_owner, (), {}).result(timeout=10),
                "second",
            )
            self.assertIsNone(pool.submit(read_owner).result(timeout=10))


if __name__ == "__main__":
    unittest.main()
