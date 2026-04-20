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

        if config.provider == "aws-bedrock":
            try:
                self._client: anthropic.Anthropic | anthropic.AnthropicBedrock = (
                    anthropic.AnthropicBedrock(
                        timeout=anthropic.Timeout(120.0, connect=10.0),
                    )
                )
            except ImportError:
                raise RuntimeError(
                    "boto3 is required for the 'aws-bedrock' provider.\n"
                    "Install it with: pip install 'tfrev[aws]'"
                )
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

    def review(self, system_prompt: str, user_prompt: str) -> APIResponse:
        """Send a review request to Claude with retry logic."""
        max_retries = 3
        base_delay = 2.0

        for attempt in range(max_retries):
            try:
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
                        f"API server error. Retrying in {delay:.0f}s ({attempt + 2}/{max_retries})...",
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
