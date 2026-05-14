"""Tests for tfrev.cli using Click's CliRunner."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from tfrev.cli import main
from tfrev.client import APIResponse

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def pass_api_response():
    return APIResponse(
        content=(FIXTURES_DIR / "response_pass.json").read_text(),
        model="claude-sonnet-4-6",
        input_tokens=1500,
        output_tokens=800,
        stop_reason="end_turn",
    )


@pytest.fixture
def fail_api_response():
    return APIResponse(
        content=(FIXTURES_DIR / "response_fail.json").read_text(),
        model="claude-sonnet-4-6",
        input_tokens=2000,
        output_tokens=1200,
        stop_reason="end_turn",
    )


@pytest.fixture
def medium_only_api_response():
    return APIResponse(
        content=(FIXTURES_DIR / "response_medium_only.json").read_text(),
        model="claude-sonnet-4-6",
        input_tokens=1500,
        output_tokens=600,
        stop_reason="end_turn",
    )


@pytest.fixture
def mock_git_diff():
    """Patch subprocess.run to return a simple diff for git diff calls."""
    diff_text = (FIXTURES_DIR / "diff_simple.diff").read_text()
    git_ok = MagicMock(returncode=0, stdout=diff_text, stderr="")
    with patch("tfrev.cli.subprocess.run", return_value=git_ok) as mock:
        yield mock


class TestVersion:
    def test_version_flag(self, runner):
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "tfrev" in result.output


class TestReviewCommand:
    @patch("tfrev.cli.ReviewClient")
    def test_basic_review_pass(self, mock_client_cls, runner, pass_api_response, mock_git_diff):
        mock_client_cls.return_value.review.return_value = pass_api_response
        plan_file = str(FIXTURES_DIR / "plan_minimal.json")

        result = runner.invoke(main, ["review", "--plan", plan_file, "--quiet"])
        assert result.exit_code == 0
        mock_client_cls.return_value.review.assert_called_once()

    @patch("tfrev.cli.ReviewClient")
    def test_review_fail_exit_code(self, mock_client_cls, runner, fail_api_response, mock_git_diff):
        mock_client_cls.return_value.review.return_value = fail_api_response
        plan_file = str(FIXTURES_DIR / "plan_minimal.json")

        result = runner.invoke(main, ["review", "--plan", plan_file, "--quiet"])
        assert result.exit_code == 1

    @patch("tfrev.cli.ReviewClient")
    def test_json_output(self, mock_client_cls, runner, pass_api_response, mock_git_diff):
        mock_client_cls.return_value.review.return_value = pass_api_response
        plan_file = str(FIXTURES_DIR / "plan_minimal.json")

        result = runner.invoke(main, ["review", "--plan", plan_file, "--output", "json", "--quiet"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["review"]["verdict"] == "PASS"

    @patch("tfrev.cli.ReviewClient")
    def test_markdown_output(self, mock_client_cls, runner, pass_api_response, mock_git_diff):
        mock_client_cls.return_value.review.return_value = pass_api_response
        plan_file = str(FIXTURES_DIR / "plan_minimal.json")

        result = runner.invoke(
            main, ["review", "--plan", plan_file, "--output", "markdown", "--quiet"]
        )
        assert result.exit_code == 0
        assert "PASS" in result.output
        assert "##" in result.output

    def test_missing_plan(self, runner):
        result = runner.invoke(main, ["review"])
        assert result.exit_code == 2

    @patch("tfrev.cli.ReviewClient")
    def test_fail_on_critical_with_critical_finding(
        self, mock_client_cls, runner, fail_api_response, mock_git_diff
    ):
        mock_client_cls.return_value.review.return_value = fail_api_response
        plan_file = str(FIXTURES_DIR / "plan_minimal.json")

        result = runner.invoke(
            main, ["review", "--plan", plan_file, "--fail-on", "critical", "--quiet"]
        )
        assert result.exit_code == 1

    @patch("tfrev.cli.ReviewClient")
    def test_fail_on_critical_with_medium_only_finding(
        self, mock_client_cls, runner, medium_only_api_response, mock_git_diff
    ):
        """--fail-on critical exits 0 when only medium findings are present."""
        mock_client_cls.return_value.review.return_value = medium_only_api_response
        plan_file = str(FIXTURES_DIR / "plan_minimal.json")

        result = runner.invoke(
            main, ["review", "--plan", plan_file, "--fail-on", "critical", "--quiet"]
        )
        assert result.exit_code == 0

    @patch("tfrev.cli.ReviewClient")
    def test_config_override(self, mock_client_cls, runner, pass_api_response, mock_git_diff):
        mock_client_cls.return_value.review.return_value = pass_api_response
        plan_file = str(FIXTURES_DIR / "plan_minimal.json")
        config_file = str(FIXTURES_DIR / "config_full.yaml")

        result = runner.invoke(
            main, ["review", "--plan", plan_file, "--config", config_file, "--quiet"]
        )
        assert result.exit_code == 0

    @patch("tfrev.cli.ReviewClient")
    def test_no_context_flag(self, mock_client_cls, runner, pass_api_response, mock_git_diff):
        mock_client_cls.return_value.review.return_value = pass_api_response
        plan_file = str(FIXTURES_DIR / "plan_minimal.json")

        result = runner.invoke(main, ["review", "--plan", plan_file, "--no-context", "--quiet"])
        assert result.exit_code == 0

    @patch("tfrev.cli.ReviewClient")
    def test_base_ref_passed_to_git(
        self, mock_client_cls, runner, pass_api_response, mock_git_diff
    ):
        mock_client_cls.return_value.review.return_value = pass_api_response
        plan_file = str(FIXTURES_DIR / "plan_minimal.json")

        result = runner.invoke(
            main, ["review", "--plan", plan_file, "--base-ref", "abc1234", "--quiet"]
        )
        assert result.exit_code == 0
        # Find the git-diff call among all subprocess invocations.
        diff_calls = [
            call
            for call in mock_git_diff.call_args_list
            if len(call.args) > 0 and "diff" in call.args[0]
        ]
        assert diff_calls, "no git-diff call was made"
        assert any("abc1234...HEAD" in call.args[0] for call in diff_calls)

    @patch("tfrev.cli.ReviewClient")
    def test_provider_flag_anthropic(
        self, mock_client_cls, runner, pass_api_response, mock_git_diff
    ):
        """--provider anthropic sets config.provider to 'anthropic'."""
        mock_client_cls.return_value.review.return_value = pass_api_response
        plan_file = str(FIXTURES_DIR / "plan_minimal.json")

        result = runner.invoke(
            main, ["review", "--plan", plan_file, "--provider", "anthropic", "--quiet"]
        )
        assert result.exit_code == 0
        config_arg = mock_client_cls.call_args[0][0]
        assert config_arg.provider == "anthropic"

    @patch("tfrev.cli.ReviewClient")
    def test_provider_flag_aws_bedrock(
        self, mock_client_cls, runner, pass_api_response, mock_git_diff
    ):
        """--provider aws-bedrock sets config.provider to 'aws-bedrock'."""
        mock_client_cls.return_value.review.return_value = pass_api_response
        plan_file = str(FIXTURES_DIR / "plan_minimal.json")

        result = runner.invoke(
            main, ["review", "--plan", plan_file, "--provider", "aws-bedrock", "--quiet"]
        )
        assert result.exit_code == 0
        config_arg = mock_client_cls.call_args[0][0]
        assert config_arg.provider == "aws-bedrock"

    def test_provider_flag_invalid_value(self, runner):
        """An unrecognised --provider value is rejected by Click before any API call."""
        plan_file = str(FIXTURES_DIR / "plan_minimal.json")
        result = runner.invoke(
            main, ["review", "--plan", plan_file, "--provider", "openai", "--quiet"]
        )
        assert result.exit_code == 2
        assert "'openai' is not one of" in result.output.lower()

    def test_runtime_error_from_client(self, runner, mock_git_diff):
        with patch("tfrev.cli.ReviewClient") as mock_client_cls:
            mock_client_cls.side_effect = RuntimeError("ANTHROPIC_API_KEY is not set")
            plan_file = str(FIXTURES_DIR / "plan_minimal.json")
            result = runner.invoke(main, ["review", "--plan", plan_file, "--quiet"])
        assert result.exit_code == 2

    def test_git_not_found(self, runner):
        with patch("tfrev.cli.subprocess.run", side_effect=FileNotFoundError):
            plan_file = str(FIXTURES_DIR / "plan_minimal.json")
            result = runner.invoke(main, ["review", "--plan", plan_file, "--quiet"])
        assert result.exit_code == 2

    def test_git_diff_timeout(self, runner, monkeypatch):
        """A TimeoutExpired from git diff should exit 2 with a clean error, not a traceback."""
        import subprocess as sp

        # Pin the base-ref lookup so the test doesn't depend on CI env vars
        # that would otherwise change which subprocess call the timeout hits.
        for var in ("GITHUB_BASE_REF", "CI_MERGE_REQUEST_TARGET_BRANCH_NAME", "CHANGE_TARGET"):
            monkeypatch.delenv(var, raising=False)

        git_check = MagicMock(returncode=0, stdout="true", stderr="")
        detect_branch = MagicMock(returncode=0)

        def side_effect(*args, **kwargs):
            call = side_effect.calls
            side_effect.calls += 1
            if call == 0:
                return git_check
            if call == 1:
                return detect_branch
            raise sp.TimeoutExpired(cmd="git diff", timeout=30)

        side_effect.calls = 0
        with patch("tfrev.cli.subprocess.run", side_effect=side_effect):
            plan_file = str(FIXTURES_DIR / "plan_minimal.json")
            result = runner.invoke(main, ["review", "--plan", plan_file, "--quiet"])
        assert result.exit_code == 2
        assert "timed out" in result.output.lower() or "timeout" in result.output.lower()

    def test_git_diff_timeout_in_empty_tree_fallback(self, runner, monkeypatch):
        """Timeout during the empty-tree fallback must also exit 2 cleanly."""
        import subprocess as sp

        # Simulate CI: base ref comes from env, so no _detect_default_branch call.
        monkeypatch.setenv("GITHUB_BASE_REF", "main")

        git_check = MagicMock(returncode=0, stdout="true", stderr="")
        empty_diff = MagicMock(returncode=0, stdout="", stderr="")

        def side_effect(*args, **kwargs):
            call = side_effect.calls
            side_effect.calls += 1
            if call == 0:
                return git_check
            if call == 1:
                return empty_diff
            raise sp.TimeoutExpired(cmd="git diff", timeout=30)

        side_effect.calls = 0
        with patch("tfrev.cli.subprocess.run", side_effect=side_effect):
            plan_file = str(FIXTURES_DIR / "plan_minimal.json")
            result = runner.invoke(main, ["review", "--plan", plan_file, "--quiet"])
        assert result.exit_code == 2, result.output
        assert "timed out" in result.output.lower() or "timeout" in result.output.lower()

    def test_git_diff_both_refs_fail(self, runner):
        fail = MagicMock(returncode=1, stdout="", stderr="unknown revision")
        with patch("tfrev.cli.subprocess.run", return_value=fail):
            plan_file = str(FIXTURES_DIR / "plan_minimal.json")
            result = runner.invoke(main, ["review", "--plan", plan_file, "--quiet"])
        assert result.exit_code == 2

    @patch("tfrev.cli.ReviewClient")
    def test_non_git_dir_skips_base_ref_prompt(self, mock_client_cls, runner, pass_api_response):
        """In a non-git directory, no --base-ref prompt should fire."""
        mock_client_cls.return_value.review.return_value = pass_api_response
        plan_file = str(FIXTURES_DIR / "plan_minimal.json")

        # Simulate `git rev-parse --is-inside-work-tree` returning non-zero,
        # i.e., we are not inside a git repo.
        not_git = MagicMock(returncode=128, stdout="", stderr="fatal: not a git repo")

        with (
            patch("tfrev.cli.subprocess.run", return_value=not_git),
            runner.isolated_filesystem(),
        ):
            # No --quiet, no --base-ref. Supply "y" to accept the send confirmation.
            result = runner.invoke(main, ["review", "--plan", plan_file], input="y\n")

        # The base-ref prompt should not fire in a non-git dir.
        assert "Continue?" not in result.output
        assert "diff against" not in result.output
        assert result.exit_code == 0, result.output

    @patch("tfrev.cli.ReviewClient")
    def test_malformed_response_exits_2(self, mock_client_cls, runner, mock_git_diff):
        """Unparseable Claude response must not silently exit 0."""
        bad_response = APIResponse(
            content="not json at all",
            model="claude-sonnet-4-6",
            input_tokens=1,
            output_tokens=1,
            stop_reason="end_turn",
        )
        mock_client_cls.return_value.review.return_value = bad_response
        plan_file = str(FIXTURES_DIR / "plan_minimal.json")

        result = runner.invoke(main, ["review", "--plan", plan_file, "--quiet"])
        assert result.exit_code == 2

    @patch("tfrev.cli.ReviewClient")
    def test_send_confirmation_declined_skips_claude(
        self, mock_client_cls, runner, pass_api_response, mock_git_diff
    ):
        """Answering 'n' to the send confirmation exits 2 without calling Claude."""
        mock_client_cls.return_value.review.return_value = pass_api_response
        plan_file = str(FIXTURES_DIR / "plan_minimal.json")

        # No --quiet: the send-confirmation prompt fires. Answer 'n'.
        # Also supply 'y' for the base-ref prompt that precedes it.
        result = runner.invoke(
            main,
            ["review", "--plan", plan_file, "--base-ref", "HEAD~1"],
            input="n\n",
        )
        assert result.exit_code == 2
        mock_client_cls.return_value.review.assert_not_called()

    @patch("tfrev.cli.ReviewClient")
    def test_no_plan_changes_skips_claude(self, mock_client_cls, runner):
        """When the plan has zero changes, tfrev exits 0 without calling Claude."""
        plan_file = str(FIXTURES_DIR / "plan_empty.json")
        result = runner.invoke(main, ["review", "--plan", plan_file])
        assert result.exit_code == 0
        mock_client_cls.return_value.review.assert_not_called()
        assert "no infrastructure changes" in result.output.lower()

    @patch("tfrev.cli.ReviewClient")
    def test_empty_diff_falls_back_to_full_state(self, mock_client_cls, runner, pass_api_response):
        """When base ref diff is empty, falls back to diffing against the empty tree."""
        mock_client_cls.return_value.review.return_value = pass_api_response
        diff_text = (FIXTURES_DIR / "diff_simple.diff").read_text()
        git_check = MagicMock(returncode=0, stdout="true", stderr="")
        detect_branch = MagicMock(returncode=0)  # _detect_default_branch: rev-parse main
        empty = MagicMock(returncode=0, stdout="", stderr="")
        full_state = MagicMock(returncode=0, stdout=diff_text, stderr="")

        toplevel = MagicMock(returncode=0, stdout="/tmp\n", stderr="")
        side_effects = [git_check, detect_branch, empty, full_state, toplevel]
        with patch("tfrev.cli.subprocess.run", side_effect=side_effects):
            plan_file = str(FIXTURES_DIR / "plan_minimal.json")
            result = runner.invoke(main, ["review", "--plan", plan_file, "--quiet"])
        assert result.exit_code == 0
        mock_client_cls.return_value.review.assert_called_once()


class TestDiffPatterns:
    @patch("tfrev.cli.ReviewClient")
    def test_default_patterns_in_git_diff(
        self, mock_client_cls, runner, pass_api_response, mock_git_diff
    ):
        """Without --diff-pattern, git diff uses *.tf and *.tfvars."""
        mock_client_cls.return_value.review.return_value = pass_api_response
        plan_file = str(FIXTURES_DIR / "plan_minimal.json")

        runner.invoke(main, ["review", "--plan", plan_file, "--base-ref", "HEAD~1", "--quiet"])
        diff_calls = [
            c.args[0] for c in mock_git_diff.call_args_list if c.args and "diff" in c.args[0]
        ]
        assert diff_calls, "no git-diff call was made"
        assert "*.tf" in diff_calls[0]
        assert "*.tfvars" in diff_calls[0]

    @patch("tfrev.cli.ReviewClient")
    def test_extra_diff_pattern_appended(
        self, mock_client_cls, runner, pass_api_response, mock_git_diff
    ):
        """--diff-pattern adds to the default patterns without replacing them."""
        mock_client_cls.return_value.review.return_value = pass_api_response
        plan_file = str(FIXTURES_DIR / "plan_minimal.json")

        runner.invoke(
            main,
            [
                "review",
                "--plan",
                plan_file,
                "--base-ref",
                "HEAD~1",
                "--diff-pattern",
                "*.yaml",
                "--quiet",
            ],
        )
        diff_calls = [
            c.args[0] for c in mock_git_diff.call_args_list if c.args and "diff" in c.args[0]
        ]
        assert diff_calls, "no git-diff call was made"
        assert "*.tf" in diff_calls[0]
        assert "*.tfvars" in diff_calls[0]
        assert "*.yaml" in diff_calls[0]

    @patch("tfrev.cli.ReviewClient")
    def test_config_diff_patterns_merged(
        self, mock_client_cls, runner, pass_api_response, mock_git_diff, tmp_path
    ):
        """diff_patterns from .tfrev.yaml are merged with the defaults."""
        mock_client_cls.return_value.review.return_value = pass_api_response
        plan_file = str(FIXTURES_DIR / "plan_minimal.json")
        config_file = tmp_path / ".tfrev.yaml"
        config_file.write_text("diff_patterns:\n  - '*.yaml'\n")

        runner.invoke(
            main,
            [
                "review",
                "--plan",
                plan_file,
                "--base-ref",
                "HEAD~1",
                "--config",
                str(config_file),
                "--quiet",
            ],
        )
        diff_calls = [
            c.args[0] for c in mock_git_diff.call_args_list if c.args and "diff" in c.args[0]
        ]
        assert diff_calls, "no git-diff call was made"
        assert "*.tf" in diff_calls[0]
        assert "*.tfvars" in diff_calls[0]
        assert "*.yaml" in diff_calls[0]

    @patch("tfrev.cli.ReviewClient")
    def test_config_and_cli_diff_patterns_combined(
        self, mock_client_cls, runner, pass_api_response, mock_git_diff, tmp_path
    ):
        """CLI --diff-pattern and config diff_patterns are both included."""
        mock_client_cls.return_value.review.return_value = pass_api_response
        plan_file = str(FIXTURES_DIR / "plan_minimal.json")
        config_file = tmp_path / ".tfrev.yaml"
        config_file.write_text("diff_patterns:\n  - '*.yaml'\n")

        runner.invoke(
            main,
            [
                "review",
                "--plan",
                plan_file,
                "--base-ref",
                "HEAD~1",
                "--config",
                str(config_file),
                "--diff-pattern",
                "*.json",
                "--quiet",
            ],
        )
        diff_calls = [
            c.args[0] for c in mock_git_diff.call_args_list if c.args and "diff" in c.args[0]
        ]
        assert diff_calls
        assert "*.tf" in diff_calls[0]
        assert "*.yaml" in diff_calls[0]
        assert "*.json" in diff_calls[0]

    @patch("tfrev.cli.ReviewClient")
    def test_multiple_extra_diff_patterns(
        self, mock_client_cls, runner, pass_api_response, mock_git_diff
    ):
        """Multiple --diff-pattern flags are all included alongside the defaults."""
        mock_client_cls.return_value.review.return_value = pass_api_response
        plan_file = str(FIXTURES_DIR / "plan_minimal.json")

        runner.invoke(
            main,
            [
                "review",
                "--plan",
                plan_file,
                "--base-ref",
                "HEAD~1",
                "--diff-pattern",
                "*.yaml",
                "--diff-pattern",
                "*.yml",
                "--quiet",
            ],
        )
        diff_calls = [
            c.args[0] for c in mock_git_diff.call_args_list if c.args and "diff" in c.args[0]
        ]
        assert diff_calls
        assert "*.tf" in diff_calls[0]
        assert "*.yaml" in diff_calls[0]
        assert "*.yml" in diff_calls[0]


class TestScanTfFiles:
    def test_default_patterns_include_only_tf(self, tmp_path):
        """By default, _scan_tf_files picks up .tf and .tfvars but not .yaml."""
        from tfrev.cli import _scan_tf_files

        (tmp_path / "main.tf").write_text('resource "null_resource" "x" {}\n')
        (tmp_path / "values.yaml").write_text("key: value\n")

        result = _scan_tf_files(tmp_path, quiet=True)
        paths = [f.path for f in result.files]
        assert any("main.tf" in p for p in paths)
        assert not any("values.yaml" in p for p in paths)

    def test_custom_pattern_includes_yaml(self, tmp_path):
        """Passing a custom pattern causes .yaml files to be included."""
        from tfrev.cli import _scan_tf_files

        (tmp_path / "main.tf").write_text('resource "null_resource" "x" {}\n')
        (tmp_path / "values.yaml").write_text("key: value\n")

        result = _scan_tf_files(tmp_path, quiet=True, patterns=["*.tf", "*.tfvars", "*.yaml"])
        paths = [f.path for f in result.files]
        assert any("main.tf" in p for p in paths)
        assert any("values.yaml" in p for p in paths)

    def test_terraform_dir_always_excluded(self, tmp_path):
        """Files under .terraform/ are excluded regardless of patterns."""
        from tfrev.cli import _scan_tf_files

        tf_dir = tmp_path / ".terraform"
        tf_dir.mkdir()
        (tf_dir / "cached.tf").write_text("# cached\n")
        (tmp_path / "main.tf").write_text('resource "null_resource" "x" {}\n')

        result = _scan_tf_files(tmp_path, quiet=True)
        paths = [f.path for f in result.files]
        assert not any(".terraform" in p for p in paths)
        assert any("main.tf" in p for p in paths)

    def test_subdirectory_files_discovered(self, tmp_path):
        """Files in subdirectories are found via the ** glob."""
        from tfrev.cli import _scan_tf_files

        subdir = tmp_path / "helm"
        subdir.mkdir()
        (subdir / "values.yaml").write_text("replicaCount: 1\n")
        (tmp_path / "main.tf").write_text('resource "null_resource" "x" {}\n')

        result = _scan_tf_files(tmp_path, quiet=True, patterns=["*.tf", "*.yaml"])
        paths = [f.path for f in result.files]
        assert any("main.tf" in p for p in paths)
        assert any("values.yaml" in p for p in paths)


class TestAutoMode:
    @patch("tfrev.cli.subprocess.run")
    @patch("tfrev.cli.Path")
    def test_no_plan_file_found(self, mock_path_cls, mock_subproc, runner):
        mock_path_cls.return_value.glob.return_value = []
        result = runner.invoke(main, ["review", "--auto", "--quiet"])
        assert result.exit_code == 2

    @patch("tfrev.cli.subprocess.run")
    @patch("tfrev.cli.Path")
    def test_terraform_not_in_path(self, mock_path_cls, mock_subproc, runner):
        mock_plan = MagicMock()
        mock_plan.exists.return_value = True
        mock_plan.__str__ = lambda self: "tfplan"
        mock_path_cls.return_value.glob.return_value = [mock_plan]
        mock_subproc.side_effect = FileNotFoundError

        result = runner.invoke(main, ["review", "--auto", "--quiet"])
        assert result.exit_code == 2

    @patch("tfrev.cli.subprocess.run")
    @patch("tfrev.cli.Path")
    def test_terraform_show_fails(self, mock_path_cls, mock_subproc, runner):
        mock_plan = MagicMock()
        mock_plan.exists.return_value = True
        mock_plan.__str__ = lambda self: "tfplan"
        mock_path_cls.return_value.glob.return_value = [mock_plan]
        mock_subproc.return_value = MagicMock(returncode=1, stderr="Error reading plan")

        result = runner.invoke(main, ["review", "--auto", "--quiet"])
        assert result.exit_code == 2

    @patch("tfrev.cli.ReviewClient")
    @patch("tfrev.cli.subprocess.run")
    @patch("tfrev.cli.Path")
    def test_auto_success(
        self, mock_path_cls, mock_subproc, mock_client_cls, runner, pass_api_response
    ):
        mock_plan = MagicMock()
        mock_plan.exists.return_value = True
        mock_plan.__str__ = lambda self: "tfplan"
        mock_path_cls.return_value.glob.return_value = [mock_plan]

        plan_json = json.loads((FIXTURES_DIR / "plan_minimal.json").read_text())
        diff_text = (FIXTURES_DIR / "diff_simple.diff").read_text()
        mock_subproc.side_effect = [
            MagicMock(returncode=0, stdout=json.dumps(plan_json), stderr=""),
            MagicMock(returncode=0, stdout="true", stderr=""),  # git check
            MagicMock(returncode=0),  # _detect_default_branch: rev-parse main
            MagicMock(returncode=0, stdout=diff_text, stderr=""),  # git diff
            MagicMock(returncode=0, stdout="/tmp\n", stderr=""),  # git toplevel
        ]
        mock_client_cls.return_value.review.return_value = pass_api_response

        result = runner.invoke(main, ["review", "--auto", "--quiet"])
        assert result.exit_code == 0
        mock_client_cls.return_value.review.assert_called_once()

    @patch("tfrev.cli.ReviewClient")
    @patch("tfrev.cli.subprocess.run")
    @patch("tfrev.cli.Path")
    def test_git_diff_falls_back_to_origin(
        self, mock_path_cls, mock_subproc, mock_client_cls, runner, pass_api_response
    ):
        mock_plan = MagicMock()
        mock_plan.exists.return_value = True
        mock_plan.__str__ = lambda self: "tfplan"
        mock_path_cls.return_value.glob.return_value = [mock_plan]

        plan_json = json.loads((FIXTURES_DIR / "plan_minimal.json").read_text())
        diff_text = (FIXTURES_DIR / "diff_simple.diff").read_text()
        mock_subproc.side_effect = [
            MagicMock(returncode=0, stdout=json.dumps(plan_json), stderr=""),
            MagicMock(returncode=0, stdout="true", stderr=""),  # git check
            MagicMock(returncode=0),  # _detect_default_branch: rev-parse main
            MagicMock(returncode=1, stdout="", stderr="unknown revision"),  # git diff main...HEAD
            MagicMock(returncode=1, stdout="", stderr="unknown revision"),  # git diff main..HEAD
            MagicMock(returncode=0, stdout=diff_text, stderr=""),  # git diff origin/main...HEAD
            MagicMock(returncode=0, stdout="/tmp\n", stderr=""),  # git toplevel
        ]
        mock_client_cls.return_value.review.return_value = pass_api_response

        result = runner.invoke(main, ["review", "--auto", "--quiet"])
        assert result.exit_code == 0

    @patch("tfrev.cli.ReviewClient")
    @patch("tfrev.cli.subprocess.run")
    @patch("tfrev.cli.Path")
    def test_shallow_clone_falls_back_to_two_dot(
        self, mock_path_cls, mock_subproc, mock_client_cls, runner, pass_api_response
    ):
        """In a shallow clone, three-dot diff fails but two-dot diff succeeds."""
        mock_plan = MagicMock()
        mock_plan.exists.return_value = True
        mock_plan.__str__ = lambda self: "tfplan"
        mock_path_cls.return_value.glob.return_value = [mock_plan]

        plan_json = json.loads((FIXTURES_DIR / "plan_minimal.json").read_text())
        diff_text = (FIXTURES_DIR / "diff_simple.diff").read_text()
        mock_subproc.side_effect = [
            MagicMock(returncode=0, stdout=json.dumps(plan_json), stderr=""),
            MagicMock(returncode=0, stdout="true", stderr=""),  # git check
            MagicMock(returncode=0),  # _detect_default_branch: rev-parse main
            MagicMock(
                returncode=128, stdout="", stderr="no merge base"
            ),  # git diff main...HEAD (shallow)
            MagicMock(returncode=0, stdout=diff_text, stderr=""),  # git diff main..HEAD (two-dot)
            MagicMock(returncode=0, stdout="/tmp\n", stderr=""),  # git toplevel
        ]
        mock_client_cls.return_value.review.return_value = pass_api_response

        result = runner.invoke(main, ["review", "--auto", "--quiet"])
        assert result.exit_code == 0
        mock_client_cls.return_value.review.assert_called_once()

    @patch("tfrev.cli.ReviewClient")
    @patch("tfrev.cli.subprocess.run")
    @patch("tfrev.cli.Path")
    def test_both_git_diffs_fail_falls_back(
        self, mock_path_cls, mock_subproc, mock_client_cls, runner, pass_api_response
    ):
        """When both base and origin/base diffs fail, falls back to empty-tree diff."""
        mock_plan = MagicMock()
        mock_plan.exists.return_value = True
        mock_plan.__str__ = lambda self: "tfplan"
        mock_path_cls.return_value.glob.return_value = [mock_plan]

        plan_json = json.loads((FIXTURES_DIR / "plan_minimal.json").read_text())
        diff_text = (FIXTURES_DIR / "diff_simple.diff").read_text()
        mock_subproc.side_effect = [
            MagicMock(returncode=0, stdout=json.dumps(plan_json), stderr=""),
            MagicMock(returncode=0, stdout="true", stderr=""),  # git check
            MagicMock(returncode=0),  # _detect_default_branch: rev-parse main
            MagicMock(returncode=1, stdout="", stderr="unknown revision"),  # git diff main...HEAD
            MagicMock(returncode=1, stdout="", stderr="unknown revision"),  # git diff main..HEAD
            MagicMock(
                returncode=1, stdout="", stderr="unknown revision"
            ),  # git diff origin/main...HEAD
            MagicMock(
                returncode=1, stdout="", stderr="unknown revision"
            ),  # git diff origin/main..HEAD
            MagicMock(returncode=0, stdout=diff_text, stderr=""),  # empty-tree fallback
            MagicMock(returncode=0, stdout="/tmp\n", stderr=""),  # git toplevel
        ]
        mock_client_cls.return_value.review.return_value = pass_api_response

        result = runner.invoke(main, ["review", "--auto", "--quiet"])
        assert result.exit_code == 0
