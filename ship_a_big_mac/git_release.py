"""Read a local Git repository without sending source code anywhere."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
import hashlib
import subprocess


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


def analyze_repository(
    path: str | Path = ".",
    *,
    since_days: int = 14,
    include_names: bool = False,
) -> ReleaseContext:
    repo = Path(path).expanduser().resolve()
    if since_days < 1 or since_days > 365:
        raise ValueError("since_days must be between 1 and 365")
    root = Path(_git(repo, "rev-parse", "--show-toplevel"))
    branch = _git(root, "branch", "--show-current", check=False) or "detached"
    has_head = bool(_git(root, "rev-parse", "--verify", "HEAD", check=False))
    version = _git(root, "describe", "--tags", "--abbrev=0", check=False) if has_head else ""
    if not version:
        version = _git(root, "rev-parse", "--short", "HEAD") if has_head else "unreleased"

    raw_authors = _git(
        root,
        "log",
        f"--since={since_days}.days",
        "--format=%an%x1f%ae",
        check=False,
    ).splitlines()
    identities = [line for line in raw_authors if line]
    counts = Counter(identities)
    ordered = [identity for identity, _ in counts.most_common()]
    if include_names:
        contributors = tuple(identity.split("\x1f", 1)[0] for identity in ordered)
    else:
        contributors = tuple(_private_label(identity, i + 1) for i, identity in enumerate(ordered))

    files, insertions, deletions = _change_stats(root, since_days)
    commits = len(identities)
    weight = commits + files // 2 + (insertions + deletions) // 250
    intensity = "hotfix" if weight <= 4 else "regular" if weight <= 18 else "major"
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
    )
