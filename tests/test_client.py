"""Tests for tfrev.client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import anthropic
import pytest

from tfrev.client import APIResponse, ReviewClient
from tfrev.config import TfrevConfig


@pytest.fixture
def config():
    return TfrevConfig()


@pytest.fixture
def mock_anthropic_response():
    block = MagicMock()
    block.text = '{"verdict": "PASS"}'
    response = MagicMock()
    response.content = [block]
    response.model = "claude-sonnet-4-6"
    response.usage.input_tokens = 100
    response.usage.output_tokens = 50
    response.stop_reason = "end_turn"
    return response


class TestReviewClientInit:
    def test_missing_api_key_raises(self, config, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            ReviewClient(config)

    def test_initializes_with_api_key(self, config, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        client = ReviewClient(config)
        assert isinstance(client._client, anthropic.Anthropic)


class TestReviewClientReview:
    def test_successful_call(self, config, monkeypatch, mock_anthropic_response):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        with patch("tfrev.client.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_anthropic_response
            client = ReviewClient(config)
            result = client.review("system", "user")

        assert isinstance(result, APIResponse)
        assert result.content == '{"verdict": "PASS"}'
        assert result.model == "claude-sonnet-4-6"
        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.stop_reason == "end_turn"

    def test_rate_limit_retries_then_raises(self, config, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        with patch("tfrev.client.anthropic.Anthropic") as mock_cls:
            with patch("tfrev.client.time.sleep"):
                mock_cls.return_value.messages.create.side_effect = anthropic.RateLimitError(
                    message="rate limited", response=MagicMock(), body={}
                )
                client = ReviewClient(config)
                with pytest.raises(RuntimeError, match="Rate limit exceeded"):
                    client.review("system", "user")

                assert mock_cls.return_value.messages.create.call_count == 3

    def test_internal_server_error_retries_then_raises(self, config, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        with patch("tfrev.client.anthropic.Anthropic") as mock_cls:
            with patch("tfrev.client.time.sleep"):
                mock_cls.return_value.messages.create.side_effect = anthropic.InternalServerError(
                    message="overloaded", response=MagicMock(), body={}
                )
                client = ReviewClient(config)
                with pytest.raises(RuntimeError, match="server error"):
                    client.review("system", "user")

                assert mock_cls.return_value.messages.create.call_count == 3

    def test_auth_error_raises_immediately(self, config, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-bad")
        with patch("tfrev.client.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.side_effect = anthropic.AuthenticationError(
                message="invalid key", response=MagicMock(), body={}
            )
            client = ReviewClient(config)
            with pytest.raises(RuntimeError, match="Invalid ANTHROPIC_API_KEY"):
                client.review("system", "user")

            # No retries for auth errors
            assert mock_cls.return_value.messages.create.call_count == 1

    def test_api_error_retries_then_raises(self, config, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        with patch("tfrev.client.anthropic.Anthropic") as mock_cls:
            with patch("tfrev.client.time.sleep"):
                mock_cls.return_value.messages.create.side_effect = anthropic.APIError(
                    message="something went wrong", request=MagicMock(), body={}
                )
                client = ReviewClient(config)
                with pytest.raises(RuntimeError, match="failed after"):
                    client.review("system", "user")

                assert mock_cls.return_value.messages.create.call_count == 3

    def test_rate_limit_succeeds_on_retry(self, config, monkeypatch, mock_anthropic_response):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        with patch("tfrev.client.anthropic.Anthropic") as mock_cls:
            with patch("tfrev.client.time.sleep"):
                mock_cls.return_value.messages.create.side_effect = [
                    anthropic.RateLimitError(message="rate limited", response=MagicMock(), body={}),
                    mock_anthropic_response,
                ]
                client = ReviewClient(config)
                result = client.review("system", "user")

        assert result.content == '{"verdict": "PASS"}'
        assert mock_cls.return_value.messages.create.call_count == 2

    def test_multiple_content_blocks_concatenated(self, config, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        block1 = MagicMock()
        block1.text = "hello "
        block2 = MagicMock()
        block2.text = "world"
        response = MagicMock()
        response.content = [block1, block2]
        response.model = "claude-sonnet-4-6"
        response.usage.input_tokens = 10
        response.usage.output_tokens = 5
        response.stop_reason = "end_turn"

        with patch("tfrev.client.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = response
            client = ReviewClient(config)
            result = client.review("system", "user")

        assert result.content == "hello world"

    def test_stop_reason_none_becomes_unknown(self, config, monkeypatch, mock_anthropic_response):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        mock_anthropic_response.stop_reason = None
        with patch("tfrev.client.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_anthropic_response
            client = ReviewClient(config)
            result = client.review("system", "user")

        assert result.stop_reason == "unknown"
