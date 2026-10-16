"""Read a local Git repository without sending source code anywhere."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
import hashlib
import re
import subprocess
from typing import Optional


class GitAnalysisError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReleaseContext:
    repository: str
    branch: str
    version: str
    commit_count: int
    contributor_count: int
    contributors: tuple[str, ...]
    files_changed: int
    insertions: int
    deletions: int
    intensity: str
    window_days: int
    from_ref: str = ""
    to_ref: str = ""

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["contributors"] = list(self.contributors)
        return data


def _git(path: Path, *args: str, check: bool = True) -> str:
    process = subprocess.run(
        ["git", "-C", str(path), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if check and process.returncode:
        detail = process.stderr.strip() or "unknown git error"
        raise GitAnalysisError(detail)
    return process.stdout.strip()


def _private_label(identity: str, index: int) -> str:
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:4]
    return f"Contributor {index}-{digest}"


def _change_stats(path: Path, since_days: int) -> tuple[int, int, int]:
    output = _git(path, "log", f"--since={since_days}.days", "--numstat", "--format=", check=False)
    files: set[str] = set()
    insertions = deletions = 0
    for line in output.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        added, removed, filename = parts
        files.add(filename)
        if added.isdigit():
            insertions += int(added)
        if removed.isdigit():
            deletions += int(removed)
    return len(files), insertions, deletions


def _resolve_commit(path: Path, ref: str) -> str:
    """Resolve a user supplied ref to a commit without interpreting it as an option."""
    commit = _git(path, "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}", check=False)
    if not commit:
        raise GitAnalysisError(f"Git ref does not resolve to a commit: {ref}")
    return commit


def _range_change_stats(path: Path, from_commit: str, to_commit: str) -> tuple[int, int, int]:
    """Measure the net file changes between the release boundary commits."""
    output = _git(path, "diff", "--numstat", from_commit, to_commit)
    files: set[str] = set()
    insertions = deletions = 0
    for line in output.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        added, removed, filename = parts
        files.add(filename)
        if added.isdigit():
            insertions += int(added)
        if removed.isdigit():
            deletions += int(removed)
    return len(files), insertions, deletions


def _range_intensity(from_ref: str, to_ref: str, weight: int) -> str:
    """Classify a tagged release without letting commit volume set the theme."""
    pattern = re.compile(r"^[vV]?(\d+)\.(\d+)\.(\d+)")
    before, after = pattern.match(from_ref), pattern.match(to_ref)
    if before and after:
        old = tuple(int(value) for value in before.groups())
        new = tuple(int(value) for value in after.groups())
        if new[0] == old[0] and new[1] == old[1] and new[2] > old[2]:
            return "hotfix"
        if new[:2] != old[:2]:
            return "major"
    return "hotfix" if weight <= 4 else "regular" if weight <= 18 else "major"


def analyze_repository(
    path: str | Path = ".",
    *,
    since_days: int = 14,
    include_names: bool = False,
    from_tag: Optional[str] = None,
    to_ref: Optional[str] = None,
) -> ReleaseContext:
    repo = Path(path).expanduser().resolve()
    if since_days < 1 or since_days > 365:
        raise ValueError("since_days must be between 1 and 365")
    if bool(from_tag) != bool(to_ref):
        raise ValueError("from_tag and to_ref must be provided together")
    root = Path(_git(repo, "rev-parse", "--show-toplevel"))
    branch = _git(root, "branch", "--show-current", check=False) or "detached"
    has_head = bool(_git(root, "rev-parse", "--verify", "HEAD", check=False))
    version = _git(root, "describe", "--tags", "--abbrev=0", check=False) if has_head else ""
    if not version:
        version = _git(root, "rev-parse", "--short", "HEAD") if has_head else "unreleased"

    if from_tag and to_ref:
        from_commit = _resolve_commit(root, from_tag)
        to_commit = _resolve_commit(root, to_ref)
        raw_authors = _git(
            root,
            "log",
            f"{from_commit}..{to_commit}",
            "--format=%an%x1f%ae",
        ).splitlines()
        files, insertions, deletions = _range_change_stats(root, from_commit, to_commit)
        version = to_ref
    else:
        raw_authors = _git(
            root,
            "log",
            f"--since={since_days}.days",
            "--format=%an%x1f%ae",
            check=False,
        ).splitlines()
        files, insertions, deletions = _change_stats(root, since_days)
    identities = [line for line in raw_authors if line]
    counts = Counter(identities)
    ordered = [identity for identity, _ in counts.most_common()]
    if include_names:
        contributors = tuple(identity.split("\x1f", 1)[0] for identity in ordered)
    else:
        contributors = tuple(_private_label(identity, i + 1) for i, identity in enumerate(ordered))

    commits = len(identities)
    weight = commits + files // 2 + (insertions + deletions) // 250
    intensity = _range_intensity(from_tag, to_ref, weight) if from_tag and to_ref else ("hotfix" if weight <= 4 else "regular" if weight <= 18 else "major")
    return ReleaseContext(
        repository=root.name,
        branch=branch,
        version=version,
        commit_count=commits,
        contributor_count=len(ordered),
        contributors=contributors,
        files_changed=files,
        insertions=insertions,
        deletions=deletions,
        intensity=intensity,
        window_days=since_days,
        from_ref=from_tag or "",
        to_ref=to_ref or "",
    )
