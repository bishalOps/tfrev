"""Prompt builder — assembles system and user prompts for Claude."""

from __future__ import annotations

from pathlib import Path

from tfrev.config import TfrevConfig, format_policies_for_prompt
from tfrev.diff_parser import DiffSummary, format_diff_for_prompt
from tfrev.plan_parser import PlanSummary, format_plan_for_prompt
from tfrev.tf_discovery import format_context_for_prompt

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _load_template(name: str) -> str:
    """Load a prompt template from the templates directory."""
    path = _TEMPLATES_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return path.read_text(encoding="utf-8")


def build_system_prompt() -> str:
    """Load the system prompt for Claude."""
    return _load_template("system_prompt.txt")


def build_user_prompt(
    plan: PlanSummary,
    diff: DiffSummary,
    config: TfrevConfig,
    context_files: dict[str, str] | None = None,
) -> str:
    """Build the user prompt from plan data, diff, config, and context files."""
    template = _load_template("user_prompt.txt")

    plan_data = format_plan_for_prompt(plan)
    code_diff = format_diff_for_prompt(diff)
    policies_section = format_policies_for_prompt(config)
    context_files_section = format_context_for_prompt(context_files or {})

    return template.format(
        plan_data=plan_data,
        code_diff=code_diff,
        policies_section=policies_section,
        context_files_section=context_files_section,
    )


def estimate_tokens(text: str) -> int:
    """Estimate token count. Code-heavy text (like Terraform/HCL) averages ~3.5 chars/token."""
    return max(0, int(len(text) / 3.5))
