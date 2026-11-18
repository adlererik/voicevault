"""Check help-only entry points without starting builds, servers or emulators."""
import contextlib
import io
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from command_help import firmware_parser, native_parser

ROOT = Path(__file__).resolve().parents[1]
HELP = ROOT / "scripts/command_help.py"


class CommandHelpControls(unittest.TestCase):
    def invoke(self, family, *args, cwd=None):
        # -S excludes site packages: help must not depend on the simulator venv.
        return subprocess.run([sys.executable, "-S", str(HELP), family, *args],
                              cwd=cwd, text=True, capture_output=True, timeout=5)

    def test_all_command_help_and_topic_aliases_work_without_site_packages(self):
        for family, build in [("native", native_parser), ("firmware", firmware_parser)]:
            _, topics = build()
            for topic in topics:
                with self.subTest(family=family, topic=topic):
                    direct = self.invoke(family, topic, "--help")
                    alias = self.invoke(family, "help", topic)
                    self.assertEqual(direct.returncode, 0, direct.stderr)
                    self.assertEqual(alias.returncode, 0, alias.stderr)
                    self.assertEqual(direct.stdout, alias.stdout)
                    self.assertIn("Examples:", direct.stdout)
                    self.assertNotIn("Traceback", direct.stderr)

    def test_top_level_help_and_no_arguments_are_equivalent(self):
        for family in ["native", "firmware"]:
            with self.subTest(family=family):
                plain = self.invoke(family)
                flag = self.invoke(family, "--help")
                self.assertEqual(plain.returncode, 0)
                self.assertEqual(plain.stdout, flag.stdout)
                self.assertIn("LABS_GUIDE.md", flag.stdout)

    def test_unknown_topic_has_a_usage_error_instead_of_running_work(self):
        result = self.invoke("firmware", "help", "does-not-exist")
        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid choice", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_native_launcher_help_works_in_checkout_without_runtime_or_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "scripts").mkdir()
            shutil.copy2(ROOT / "lab", root / "lab")
            shutil.copy2(HELP, root / "scripts/command_help.py")
            for args in [[], ["--help"], ["demo", "--help"], ["help", "watch"]]:
                with self.subTest(args=args):
                    result = subprocess.run([str(root / "lab"), *args], cwd=root,
                                            text=True, capture_output=True, timeout=5)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("usage: ./lab", result.stdout)
            self.assertEqual(sorted(p.name for p in root.iterdir()), ["lab", "scripts"])

    def test_native_duration_range_is_preserved(self):
        parser, _ = native_parser()
        for seconds in [8, 30]:
            self.assertEqual(parser.parse_args(["demo", "--seconds", str(seconds)]).seconds, seconds)
        for seconds in [0, 7, 31]:
            with self.subTest(seconds=seconds), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                parser.parse_args(["demo", "--seconds", str(seconds)])

    def test_existing_firmware_options_and_defaults_are_preserved(self):
        parser, _ = firmware_parser()
        self.assertEqual(parser.parse_args(["run"]).seconds, .03)
        device = parser.parse_args(["device"])
        self.assertEqual((device.wall_seconds, device.attack, device.self_test), (3600, "none", False))
        self.assertFalse(device.auto_call)
        self.assertTrue(parser.parse_args(["device", "--auto-call", "--attack", "tamper"]).auto_call)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(["device", "--self-test", "--auto-call"])
        run = parser.parse_args(["run", "--elf", "/tmp/example.elf", "--report-symbol", "REPORT", "--audio-fixture", "--power-fixture"])
        self.assertEqual(run.elf, Path("/tmp/example.elf"))
        self.assertEqual(run.report_symbol, "REPORT")
        self.assertTrue(run.audio_fixture and run.power_fixture)
        self.assertTrue(parser.parse_args(["screen", "--stop"]).stop)
        self.assertTrue(parser.parse_args(["debug", "--smoke"]).smoke)

    def test_help_does_not_change_published_run_pointers(self):
        pointers = [ROOT / ".lab-runs/current.json", ROOT / ".lab-runs/firmware-lab/current.json"]
        before = {p: p.read_bytes() if p.exists() else None for p in pointers}
        for family in ["native", "firmware"]:
            self.assertEqual(self.invoke(family, "--help").returncode, 0)
        self.assertEqual(before, {p: p.read_bytes() if p.exists() else None for p in pointers})


if __name__ == "__main__":
    unittest.main(verbosity=2)
