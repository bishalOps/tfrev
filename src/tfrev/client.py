"""API client wrapper with retry logic — supports Anthropic and AWS Bedrock providers."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

import anthropic
import click

from tfrev.config import TfrevConfig


@dataclass
class APIResponse:
    """Wrapper for Claude API response."""

    content: str
    model: str
    input_tokens: int
    output_tokens: int
    stop_reason: str


class ReviewClient:
    """Client for sending review requests to Claude (direct or via AWS Bedrock)."""

    def __init__(self, config: TfrevConfig):
        self.config = config
        self._boto3_bedrock_client = None

        if config.provider == "aws-bedrock":
            try:
                import boto3
            except ImportError as exc:
                raise RuntimeError(
                    "boto3 is required for the 'aws-bedrock' provider.\n"
                    "Install it with: pip install 'tfrev[aws]'"
                ) from exc
            if "anthropic." in config.model:
                self._client: anthropic.Anthropic | anthropic.AnthropicBedrock = (
                    anthropic.AnthropicBedrock(
                        timeout=anthropic.Timeout(120.0, connect=10.0),
                    )
                )
            else:
                # Non-Claude models (e.g. DeepSeek) must use boto3 converse API directly
                self._boto3_bedrock_client = boto3.client(
                    "bedrock-runtime",
                    config=boto3.session.Config(connect_timeout=10, read_timeout=120),
                )
                self._client = None  # type: ignore[assignment]
        else:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY environment variable is not set.\n"
                    "Get your API key from https://console.anthropic.com/\n"
                    "Then set it: export ANTHROPIC_API_KEY=<your-key>"
                )
            self._client = anthropic.Anthropic(
                api_key=api_key,
                timeout=anthropic.Timeout(120.0, connect=10.0),
            )

    def _review_via_bedrock_converse(self, system_prompt: str, user_prompt: str) -> APIResponse:
        """Send a review request using boto3 Bedrock converse API (non-Claude models)."""
        assert self._boto3_bedrock_client is not None
        response = self._boto3_bedrock_client.converse(
            modelId=self.config.model,
            system=[{"text": system_prompt}],
            messages=[{"role": "user", "content": [{"text": user_prompt}]}],
            inferenceConfig={"maxTokens": self.config.max_tokens},
        )
        content = ""
        for block in response.get("output", {}).get("message", {}).get("content", []):
            if "text" in block:
                content += block["text"]
        usage = response.get("usage", {})
        return APIResponse(
            content=content,
            model=self.config.model,
            input_tokens=usage.get("inputTokens", 0),
            output_tokens=usage.get("outputTokens", 0),
            stop_reason=response.get("stopReason") or "unknown",
        )

    def review(self, system_prompt: str, user_prompt: str) -> APIResponse:
        """Send a review request to Claude with retry logic."""
        max_retries = 3
        base_delay = 2.0

        for attempt in range(max_retries):
            try:
                if self._boto3_bedrock_client is not None:
                    return self._review_via_bedrock_converse(system_prompt, user_prompt)

                response = self._client.messages.create(
                    model=self.config.model,
                    max_tokens=self.config.max_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )

                # Extract text content
                content = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        content += block.text

                return APIResponse(
                    content=content,
                    model=response.model,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    stop_reason=response.stop_reason or "unknown",
                )

            except anthropic.RateLimitError as exc:
                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    click.echo(
                        f"Rate limited. Retrying in {delay:.0f}s ({attempt + 2}/{max_retries})...",
                        err=True,
                    )
                    time.sleep(delay)
                else:
                    raise RuntimeError("Rate limit exceeded after all retries.") from exc

            except anthropic.InternalServerError as exc:
                # Covers HTTP 529 (overloaded) and other 5xx errors
                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    click.echo(
                        f"API server error. Retrying in {delay:.0f}s"
                        f" ({attempt + 2}/{max_retries})...",
                        err=True,
                    )
                    time.sleep(delay)
                else:
                    raise RuntimeError("API server error. Try again later.") from exc

            except anthropic.AuthenticationError as exc:
                if self.config.provider == "aws-bedrock":
                    raise RuntimeError(
                        "AWS authentication failed. Check your credentials and that the "
                        "requested model is enabled in your AWS account's Bedrock console."
                    ) from exc
                raise RuntimeError(
                    "Invalid ANTHROPIC_API_KEY. Check your key at https://console.anthropic.com/"
                ) from exc

            except anthropic.PermissionDeniedError as exc:
                if self.config.provider == "aws-bedrock":
                    raise RuntimeError(
                        "AWS Bedrock access denied. Ensure your IAM role/user has the "
                        "'bedrock:InvokeModel' permission for the requested model."
                    ) from exc
                raise RuntimeError(
                    "API key lacks required permissions. "
                    "Check your key's workspace and permissions at https://console.anthropic.com/"
                ) from exc

            except anthropic.APIError as exc:
                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    click.echo(f"API error: {exc}. Retrying in {delay:.0f}s...", err=True)
                    time.sleep(delay)
                else:
                    raise RuntimeError(
                        f"API call failed after {max_retries} attempts: {exc}"
                    ) from exc

            except Exception as exc:
                # Catch botocore credential/config errors that escape the anthropic SDK wrapper
                if type(exc).__module__.startswith("botocore"):
                    raise RuntimeError(
                        f"AWS error: {exc}\n"
                        "Ensure AWS credentials are configured via environment variables "
                        "(AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY), ~/.aws/credentials, "
                        "or an IAM instance role."
                    ) from exc
                raise

        # Should not reach here, but satisfy type checker
        raise RuntimeError("Unexpected retry loop exit")
