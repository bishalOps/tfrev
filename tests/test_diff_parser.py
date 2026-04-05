"""Tests for tfrev.diff_parser."""

from __future__ import annotations

import pytest

from tfrev.diff_parser import (
    DiffSummary,
    FileDiff,
    filter_diff,
    format_diff_for_prompt,
    load_diff_file,
    parse_diff,
)


class TestParseDiff:
    def test_simple_file_count(self, simple_diff_text):
        summary = parse_diff(simple_diff_text)
        assert summary.total_files == 1

    def test_simple_file_path(self, simple_diff_text):
        summary = parse_diff(simple_diff_text)
        assert summary.files[0].path == "main.tf"

    def test_simple_additions_deletions(self, simple_diff_text):
        summary = parse_diff(simple_diff_text)
        assert summary.total_additions == 3
        assert summary.total_deletions == 3

    def test_multifile_count(self, multifile_diff_text):
        summary = parse_diff(multifile_diff_text)
        assert summary.total_files == 4

    def test_added_file(self, multifile_diff_text):
        summary = parse_diff(multifile_diff_text)
        added = [f for f in summary.files if f.status == "added"]
        assert len(added) == 1
        assert added[0].path == "security.tf"

    def test_deleted_file(self, multifile_diff_text):
        summary = parse_diff(multifile_diff_text)
        deleted = [f for f in summary.files if f.status == "deleted"]
        assert len(deleted) == 1
        assert deleted[0].path == "old_db.tf"

    def test_renamed_file(self, multifile_diff_text):
        summary = parse_diff(multifile_diff_text)
        renamed = [f for f in summary.files if f.status == "renamed"]
        assert len(renamed) == 1
        assert renamed[0].path == "variables.tf"
        assert renamed[0].old_path == "variables_old.tf"

    def test_empty_diff(self, empty_diff_text):
        summary = parse_diff(empty_diff_text)
        assert summary.total_files == 0
        assert summary.total_additions == 0
        assert summary.total_deletions == 0

    def test_hunk_properties(self, simple_diff_text):
        summary = parse_diff(simple_diff_text)
        hunk = summary.files[0].hunks[0]
        assert hunk.old_start == 1
        assert hunk.new_start == 1
        assert len(hunk.additions) == 3
        assert len(hunk.deletions) == 3

    def test_no_newline_marker(self):
        diff_text = (
            "diff --git a/test.tf b/test.tf\n"
            "--- a/test.tf\n"
            "+++ b/test.tf\n"
            "@@ -1,2 +1,2 @@\n"
            "-old line\n"
            "+new line\n"
            "\\ No newline at end of file\n"
        )
        summary = parse_diff(diff_text)
        assert summary.total_files == 1
        assert summary.total_additions == 1
        assert summary.total_deletions == 1


class TestLoadDiffFile:
    def test_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_diff_file("/nonexistent/changes.diff")

    def test_valid_file(self, fixtures_dir):
        summary = load_diff_file(str(fixtures_dir / "diff_simple.diff"))
        assert summary.total_files == 1


class TestFilterDiff:
    def test_no_patterns(self):
        summary = DiffSummary(files=[FileDiff(path="main.tf"), FileDiff(path="backend.tf")])
        result = filter_diff(summary, [])
        assert len(result.files) == 2

    def test_filter_by_pattern(self):
        summary = DiffSummary(
            files=[
                FileDiff(path="main.tf"),
                FileDiff(path="backend.tf"),
                FileDiff(path="prod.auto.tfvars"),
            ]
        )
        result = filter_diff(summary, ["*.auto.tfvars", "backend.tf"])
        assert len(result.files) == 1
        assert result.files[0].path == "main.tf"

    def test_glob_pattern(self):
        summary = DiffSummary(
            files=[
                FileDiff(path="main.tf"),
                FileDiff(path="test.auto.tfvars"),
                FileDiff(path="dev.auto.tfvars"),
            ]
        )
        result = filter_diff(summary, ["*.auto.tfvars"])
        assert len(result.files) == 1

    def test_no_matches(self):
        summary = DiffSummary(files=[FileDiff(path="main.tf")])
        result = filter_diff(summary, ["*.py"])
        assert len(result.files) == 1


class TestFormatDiffForPrompt:
    def test_contains_status_labels(self, multifile_diff_text):
        summary = parse_diff(multifile_diff_text)
        output = format_diff_for_prompt(summary)
        assert "[MODIFIED]" in output
        assert "[NEW]" in output
        assert "[DELETED]" in output
        assert "[RENAMED]" in output

    def test_contains_file_stats(self, simple_diff_text):
        summary = parse_diff(simple_diff_text)
        output = format_diff_for_prompt(summary)
        assert "Files changed: 1" in output
        assert "+3 additions" in output
        assert "-3 deletions" in output

    def test_empty_diff_format(self, empty_diff_text):
        summary = parse_diff(empty_diff_text)
        output = format_diff_for_prompt(summary)
        assert "Files changed: 0" in output
