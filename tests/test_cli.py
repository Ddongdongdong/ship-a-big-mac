from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest


class CLITests(unittest.TestCase):
    def test_demo_generates_svg_without_token(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "receipt.svg"
            env = {"PATH": os.environ.get("PATH", "")}
            process = subprocess.run(
                [sys.executable, "-m", "ship_a_big_mac", "demo", "--output", str(output)],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertTrue(output.exists())
            self.assertIn("SYNTHETIC DEMO", process.stdout)
            self.assertIn("DEMO · NOT QUOTED", output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
