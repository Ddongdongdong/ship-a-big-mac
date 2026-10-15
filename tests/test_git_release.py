from pathlib import Path
import subprocess
import tempfile
import unittest

from ship_a_big_mac.git_release import analyze_repository


class GitReleaseTests(unittest.TestCase):
    def _git(self, repo: Path, *args: str) -> None:
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)

    def test_analysis_anonymizes_contributors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            self._git(repo, "init", "-q")
            self._git(repo, "config", "user.name", "Private Person")
            self._git(repo, "config", "user.email", "private@example.com")
            (repo / "hello.txt").write_text("hello\n", encoding="utf-8")
            self._git(repo, "add", "hello.txt")
            self._git(repo, "commit", "-qm", "private subject")
            context = analyze_repository(repo)
            self.assertEqual(context.commit_count, 1)
            self.assertEqual(context.contributor_count, 1)
            self.assertTrue(context.contributors[0].startswith("Contributor 1-"))
            self.assertNotIn("Private Person", context.contributors[0])
            self.assertEqual(context.files_changed, 1)

    def test_empty_repository_is_reported_as_unreleased(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            self._git(repo, "init", "-q")
            context = analyze_repository(repo)
            self.assertEqual(context.version, "unreleased")
            self.assertEqual(context.commit_count, 0)


if __name__ == "__main__":
    unittest.main()
