"""Tests for tfrev.prompt."""

from __future__ import annotations

from tfrev.config import PolicyRule, TfrevConfig
from tfrev.prompt import build_system_prompt, build_user_prompt, estimate_tokens


class TestBuildSystemPrompt:
    def test_returns_nonempty(self):
        prompt = build_system_prompt()
        assert len(prompt) > 100

    def test_contains_terraform(self):
        prompt = build_system_prompt()
        assert "Terraform" in prompt

    def test_contains_json_schema(self):
        prompt = build_system_prompt()
        assert '"verdict"' in prompt
        assert '"findings"' in prompt


class TestBuildUserPrompt:
    def test_contains_plan_data(self, minimal_plan, simple_diff, default_config):
        prompt = build_user_prompt(minimal_plan, simple_diff, default_config)
        assert "aws_instance.web" in prompt

    def test_contains_diff_data(self, minimal_plan, simple_diff, default_config):
        prompt = build_user_prompt(minimal_plan, simple_diff, default_config)
        assert "main.tf" in prompt

    def test_with_policies(self, minimal_plan, simple_diff):
        config = TfrevConfig(policies=[PolicyRule(name="test-policy", description="A test")])
        prompt = build_user_prompt(minimal_plan, simple_diff, config)
        assert "test-policy" in prompt

    def test_with_context_files(self, minimal_plan, simple_diff, default_config):
        context = {"variables.tf": 'variable "region" {\n  default = "us-east-1"\n}'}
        prompt = build_user_prompt(minimal_plan, simple_diff, default_config, context_files=context)
        assert "variables.tf" in prompt
        assert "us-east-1" in prompt

    def test_without_context_files(self, minimal_plan, simple_diff, default_config):
        prompt = build_user_prompt(minimal_plan, simple_diff, default_config)
        assert "No additional source files" in prompt


class TestEstimateTokens:
    def test_basic(self):
        text = "a" * 400
        tokens = estimate_tokens(text)
        assert tokens > 0
        assert tokens <= 400  # should be less than char count

    def test_empty(self):
        assert estimate_tokens("") == 0

    def test_short(self):
        tokens = estimate_tokens("hi")
        assert tokens >= 0
