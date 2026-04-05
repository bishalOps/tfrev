"""Parse unified git diff output into structured format."""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field


@dataclass
class DiffHunk:
    """A single hunk from a unified diff."""

    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[str]  # Raw hunk lines including +/- prefixes

    @property
    def additions(self) -> list[str]:
        return [line[1:] for line in self.lines if line.startswith("+")]

    @property
    def deletions(self) -> list[str]:
        return [line[1:] for line in self.lines if line.startswith("-")]


@dataclass
class FileDiff:
    """Diff for a single file."""

    path: str
    old_path: str | None = None  # Set if file was renamed
    status: str = "modified"  # added, modified, deleted, renamed
    hunks: list[DiffHunk] = field(default_factory=list)

    @property
    def total_additions(self) -> int:
        return sum(len(h.additions) for h in self.hunks)

    @property
    def total_deletions(self) -> int:
        return sum(len(h.deletions) for h in self.hunks)


@dataclass
class DiffSummary:
    """Parsed summary of a git diff."""

    files: list[FileDiff]

    @property
    def total_files(self) -> int:
        return len(self.files)

    @property
    def total_additions(self) -> int:
        return sum(f.total_additions for f in self.files)

    @property
    def total_deletions(self) -> int:
        return sum(f.total_deletions for f in self.files)


# Regex patterns
_DIFF_HEADER = re.compile(r"^diff --git a/(.*) b/(.*)")
_HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
_FILE_OLD = re.compile(r"^--- (?:a/)?(.*)")
_FILE_NEW = re.compile(r"^\+\+\+ (?:b/)?(.*)")


def parse_diff(diff_text: str) -> DiffSummary:
    """Parse unified diff text into a DiffSummary."""
    files: list[FileDiff] = []
    current_file: FileDiff | None = None
    current_hunk_lines: list[str] = []
    current_hunk_header: tuple | None = None

    def _flush_hunk():
        nonlocal current_hunk_lines, current_hunk_header
        if current_hunk_header and current_file:
            old_start, old_count, new_start, new_count = current_hunk_header
            current_file.hunks.append(
                DiffHunk(
                    old_start=old_start,
                    old_count=old_count,
                    new_start=new_start,
                    new_count=new_count,
                    lines=current_hunk_lines,
                )
            )
        current_hunk_lines = []
        current_hunk_header = None

    for line in diff_text.splitlines():
        # New file diff
        diff_match = _DIFF_HEADER.match(line)
        if diff_match:
            _flush_hunk()
            old_path, new_path = diff_match.group(1), diff_match.group(2)

            status = "modified"
            if old_path != new_path:
                status = "renamed"

            current_file = FileDiff(
                path=new_path, old_path=old_path if old_path != new_path else None, status=status
            )
            files.append(current_file)
            continue

        # File status indicators
        if line.startswith("new file"):
            if current_file:
                current_file.status = "added"
            continue
        if line.startswith("deleted file"):
            if current_file:
                current_file.status = "deleted"
            continue

        # Skip --- and +++ lines (we already have paths from diff header)
        if _FILE_OLD.match(line) or _FILE_NEW.match(line):
            continue

        # Hunk header
        hunk_match = _HUNK_HEADER.match(line)
        if hunk_match:
            _flush_hunk()
            current_hunk_header = (
                int(hunk_match.group(1)),
                int(hunk_match.group(2) or "1"),
                int(hunk_match.group(3)),
                int(hunk_match.group(4) or "1"),
            )
            current_hunk_lines = []
            continue

        # Hunk content lines
        if current_hunk_header is not None:
            if line.startswith("+") or line.startswith("-") or line.startswith(" "):
                current_hunk_lines.append(line)
            elif line.startswith("\\"):
                # "\ No newline at end of file" — skip
                continue

    # Flush final hunk
    _flush_hunk()

    return DiffSummary(files=files)


def load_diff_file(path: str) -> DiffSummary:
    """Load and parse a diff file."""
    from pathlib import Path

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Diff file not found: {path}")

    return parse_diff(p.read_text(encoding="utf-8", errors="replace"))


def filter_diff(summary: DiffSummary, ignore_patterns: list[str]) -> DiffSummary:
    """Return a new DiffSummary with files matching ignore patterns removed."""
    if not ignore_patterns:
        return summary
    filtered = [
        f for f in summary.files if not any(fnmatch.fnmatch(f.path, pat) for pat in ignore_patterns)
    ]
    return DiffSummary(files=filtered)


def format_diff_for_prompt(summary: DiffSummary) -> str:
    """Format a DiffSummary for inclusion in the Claude prompt.

    Returns the raw diff text reconstructed from parsed data,
    which is cleaner and more consistent than the original input.
    """
    lines = []
    lines.append(
        f"Files changed: {summary.total_files} "
        f"(+{summary.total_additions} additions, -{summary.total_deletions} deletions)"
    )
    lines.append("")

    for f in summary.files:
        status_label = {
            "added": "[NEW]",
            "deleted": "[DELETED]",
            "renamed": "[RENAMED]",
            "modified": "[MODIFIED]",
        }.get(f.status, "[UNKNOWN]")

        if f.old_path:
            lines.append(f"{status_label} {f.old_path} -> {f.path}")
        else:
            lines.append(f"{status_label} {f.path}")

        for hunk in f.hunks:
            lines.append(
                f"@@ -{hunk.old_start},{hunk.old_count} +{hunk.new_start},{hunk.new_count} @@"
            )
            for hline in hunk.lines:
                lines.append(hline)
        lines.append("")

    return "\n".join(lines)
