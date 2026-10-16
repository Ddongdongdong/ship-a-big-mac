from pathlib import Path
import subprocess
import tempfile
import unittest

from ship_a_big_mac.git_release import analyze_repository


class GitReleaseTests(unittest.TestCase):
    def _git(self, repo: Path, *args: str) -> None:
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)

    def _commit(self, repo: Path, filename: str, content: str, name: str, email: str) -> None:
        (repo / filename).write_text(content, encoding="utf-8")
        self._git(repo, "add", filename)
        subprocess.run(
            ["git", "-C", str(repo), "-c", f"user.name={name}", "-c", f"user.email={email}", "commit", "-m", f"change {filename}"],
            check=True,
            capture_output=True,
        )

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

    def test_tag_range_includes_hotfix_merge_and_excludes_later_tag(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            self._git(repo, "init", "-q")
            self._git(repo, "config", "user.name", "Maintainer")
            self._git(repo, "config", "user.email", "maintainer@example.com")
            self._commit(repo, "base.txt", "base\n", "Base Author", "base@example.com")
            self._git(repo, "tag", "v1.0.0")

            main_branch = subprocess.run(
                ["git", "-C", str(repo), "branch", "--show-current"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            self._commit(repo, "main.txt", "main work\n", "Main Author", "main@example.com")
            self._git(repo, "checkout", "-q", "-b", "hotfix", "v1.0.0")
            self._commit(repo, "fix.txt", "urgent fix\n", "Hotfix Author", "hotfix@example.com")
            self._git(repo, "checkout", "-q", main_branch)
            self._git(repo, "merge", "--no-ff", "hotfix", "-m", "merge hotfix")
            self._git(repo, "tag", "v1.1.0")

            self._commit(repo, "after-release.txt", "later release\n", "Later Author", "later@example.com")
            self._git(repo, "tag", "v1.1.1")

            context = analyze_repository(repo, from_tag="v1.0.0", to_ref="v1.1.0")

            self.assertEqual(context.version, "v1.1.0")
            self.assertEqual(context.from_ref, "v1.0.0")
            self.assertEqual(context.to_ref, "v1.1.0")
            self.assertEqual(context.commit_count, 3)  # main, hotfix, and merge commit
            self.assertEqual(context.contributor_count, 3)
            self.assertEqual(context.files_changed, 2)  # net diff of the release endpoints
            self.assertEqual(context.insertions, 2)
            self.assertEqual(context.deletions, 0)

            next_context = analyze_repository(repo, from_tag="v1.1.0", to_ref="v1.1.1")
            self.assertEqual(next_context.commit_count, 1)
            self.assertEqual(next_context.files_changed, 1)
            self.assertEqual(next_context.intensity, "hotfix")

    def test_release_range_requires_both_refs_and_validates_unknown_ref(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            self._git(repo, "init", "-q")
            self._commit(repo, "base.txt", "base\n", "Author", "author@example.com")
            self._git(repo, "tag", "v1")
            with self.assertRaisesRegex(ValueError, "provided together"):
                analyze_repository(repo, from_tag="v1")
            with self.assertRaisesRegex(RuntimeError, "does not resolve to a commit"):
                analyze_repository(repo, from_tag="v1", to_ref="missing")


if __name__ == "__main__":
    unittest.main()
