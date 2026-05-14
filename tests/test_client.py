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
        assert client._client.api_key == "sk-ant-test"

    def test_bedrock_claude_model_uses_anthropic_bedrock(self):
        bedrock_config = TfrevConfig(provider="aws-bedrock", model="anthropic.claude-sonnet-4-5")
        with patch("tfrev.client.anthropic.AnthropicBedrock") as mock_cls:
            with patch.dict("sys.modules", {"boto3": MagicMock()}):
                client = ReviewClient(bedrock_config)
        mock_cls.assert_called_once()
        assert client._boto3_bedrock_client is None

    def test_bedrock_non_claude_model_uses_boto3(self, monkeypatch):
        bedrock_config = TfrevConfig(provider="aws-bedrock", model="deepseek.deepseek-r1-v1:0")
        mock_boto3 = MagicMock()
        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            with patch("tfrev.client.anthropic.AnthropicBedrock") as mock_bedrock_cls:
                client = ReviewClient(bedrock_config)
        mock_bedrock_cls.assert_not_called()
        mock_boto3.client.assert_called_once_with(
            "bedrock-runtime", config=mock_boto3.session.Config.return_value
        )
        assert client._boto3_bedrock_client is not None
        assert client._client is None


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


class TestBedrockConverseReview:
    """Tests for the boto3 converse path used by non-Claude Bedrock models."""

    @pytest.fixture
    def bedrock_config(self):
        return TfrevConfig(provider="aws-bedrock", model="deepseek.deepseek-r1-v1:0")

    @pytest.fixture
    def mock_converse_response(self):
        return {
            "output": {"message": {"content": [{"text": '{"verdict": "PASS"}'}]}},
            "usage": {"inputTokens": 200, "outputTokens": 80},
            "stopReason": "end_turn",
        }

    def _make_client(self, bedrock_config, mock_boto3_client):
        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_boto3_client
        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            return ReviewClient(bedrock_config)

    def test_successful_converse_call(self, bedrock_config, mock_converse_response):
        mock_boto3_client = MagicMock()
        mock_boto3_client.converse.return_value = mock_converse_response
        client = self._make_client(bedrock_config, mock_boto3_client)

        result = client.review("system", "user")

        assert isinstance(result, APIResponse)
        assert result.content == '{"verdict": "PASS"}'
        assert result.model == "deepseek.deepseek-r1-v1:0"
        assert result.input_tokens == 200
        assert result.output_tokens == 80
        assert result.stop_reason == "end_turn"

    def test_converse_passes_correct_params(self, bedrock_config, mock_converse_response):
        mock_boto3_client = MagicMock()
        mock_boto3_client.converse.return_value = mock_converse_response
        client = self._make_client(bedrock_config, mock_boto3_client)

        client.review("my system prompt", "my user prompt")

        mock_boto3_client.converse.assert_called_once_with(
            modelId="deepseek.deepseek-r1-v1:0",
            system=[{"text": "my system prompt"}],
            messages=[{"role": "user", "content": [{"text": "my user prompt"}]}],
            inferenceConfig={"maxTokens": bedrock_config.max_tokens},
        )

    def test_converse_stop_reason_none_becomes_unknown(
        self, bedrock_config, mock_converse_response
    ):
        mock_converse_response["stopReason"] = None
        mock_boto3_client = MagicMock()
        mock_boto3_client.converse.return_value = mock_converse_response
        client = self._make_client(bedrock_config, mock_boto3_client)

        result = client.review("system", "user")

        assert result.stop_reason == "unknown"

    def test_converse_multiple_content_blocks_concatenated(self, bedrock_config):
        mock_boto3_client = MagicMock()
        mock_boto3_client.converse.return_value = {
            "output": {"message": {"content": [{"text": "hello "}, {"text": "world"}]}},
            "usage": {"inputTokens": 10, "outputTokens": 5},
            "stopReason": "end_turn",
        }
        client = self._make_client(bedrock_config, mock_boto3_client)

        result = client.review("system", "user")

        assert result.content == "hello world"
