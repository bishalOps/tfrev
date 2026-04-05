"""Output formatters for review results."""

from __future__ import annotations

import json
import textwrap

import click

from tfrev.config import TfrevConfig, severity_meets_threshold
from tfrev.response_parser import Finding, ReviewResult

# --- Severity display ---
_SEVERITY_EMOJI = {
    "critical": "\u2757",  # ❗
    "high": "\U0001f534",  # 🔴
    "medium": "\U0001f7e0",  # 🟠
    "low": "\U0001f7e1",  # 🟡
    "info": "\U0001f535",  # 🔵
}

_VERDICT_EMOJI = {
    "PASS": "\u2705",  # ✅
    "WARN": "\u26a0\ufe0f",  # ⚠️
    "FAIL": "\u274c",  # ❌
}

_SEVERITY_STYLE: dict[str, dict] = {
    "critical": {"fg": "bright_red", "bold": True},
    "high": {"fg": "red", "bold": True},
    "medium": {"fg": "yellow", "bold": True},
    "low": {"fg": "cyan", "bold": False},
    "info": {"fg": "blue", "bold": False},
}

_VERDICT_STYLE: dict[str, dict] = {
    "PASS": {"fg": "bright_green", "bold": True},
    "WARN": {"fg": "yellow", "bold": True},
    "FAIL": {"fg": "bright_red", "bold": True},
}


def _sev(text: str, severity: str) -> str:
    return click.style(text, **_SEVERITY_STYLE.get(severity, {}))


def _wrap(text: str, width: int = 90, indent: str = "  ") -> str:
    return textwrap.fill(text, width=width, initial_indent=indent, subsequent_indent=indent)


def format_json(result: ReviewResult, config: TfrevConfig) -> str:
    """Format the review result as JSON."""
    findings = _filter_findings(result, config)

    output = {
        "review": {
            "verdict": result.verdict,
            "confidence": result.confidence,
            "summary": result.summary,
            "findings": [
                {
                    "id": f.id,
                    "severity": f.severity,
                    "category": f.category,
                    "resource": f.resource,
                    "title": f.title,
                    "description": f.description,
                    "code_reference": f.code_reference,
                    "plan_reference": f.plan_reference,
                    "recommendation": f.recommendation,
                }
                for f in findings
            ],
            "stats": {
                "resources_reviewed": result.stats.resources_reviewed,
                "resources_changing": result.stats.resources_changing,
                "resources_created": result.stats.resources_created,
                "resources_updated": result.stats.resources_updated,
                "resources_deleted": result.stats.resources_deleted,
                "resources_replaced": result.stats.resources_replaced,
                "findings_by_severity": result.stats.findings_by_severity,
            },
            "unmapped_plan_changes": result.unmapped_plan_changes,
            "unmapped_code_changes": result.unmapped_code_changes,
        }
    }

    return json.dumps(output, indent=2)


def format_markdown(result: ReviewResult, config: TfrevConfig) -> str:
    """Format the review result as Markdown (for PR comments)."""
    findings = _filter_findings(result, config)
    verdict_icon = _VERDICT_EMOJI.get(result.verdict, "")

    lines = []
    lines.append(f"## {verdict_icon} Terraform Plan Review: **{result.verdict}**")
    lines.append("")
    lines.append(f"> {result.summary}")
    lines.append("")

    # Stats bar
    s = result.stats
    lines.append(
        f"**Resources:** {s.resources_reviewed} reviewed | "
        f"+{s.resources_created} create | "
        f"~{s.resources_updated} update | "
        f"-{s.resources_deleted} delete | "
        f"-/+{s.resources_replaced} replace"
    )
    lines.append(f"**Confidence:** {result.confidence:.0%}")
    lines.append("")

    # Findings
    if findings:
        lines.append("### Findings")
        lines.append("")

        for f in findings:
            sev_icon = _SEVERITY_EMOJI.get(f.severity, "")
            lines.append(f"#### {sev_icon} [{f.severity.upper()}] {f.title}")
            lines.append("")
            lines.append(f"**Resource:** `{f.resource}`")
            lines.append(f"**Category:** {f.category}")
            lines.append("")
            lines.append(f"{f.description}")
            lines.append("")

            if f.code_reference:
                file = f.code_reference.get("file", "")
                file_lines = f.code_reference.get("lines", "")
                if file:
                    lines.append(f"**Code:** `{file}` (lines {file_lines})")

            if f.plan_reference:
                action = f.plan_reference.get("action", "")
                addr = f.plan_reference.get("address", "")
                if addr:
                    lines.append(f"**Plan:** `{addr}` ({action})")

            if f.recommendation:
                lines.append("")
                lines.append(f"**Recommendation:** {f.recommendation}")

            lines.append("")
            lines.append("---")
            lines.append("")
    else:
        lines.append("No findings at or above the configured severity threshold.")
        lines.append("")

    # Unmapped changes
    if result.unmapped_plan_changes:
        lines.append("### Unmapped Plan Changes")
        lines.append("These resources changed in the plan but have no corresponding code change:")
        lines.append("")
        for addr in result.unmapped_plan_changes:
            lines.append(f"- `{addr}`")
        lines.append("")

    if result.unmapped_code_changes:
        lines.append("### Unmapped Code Changes")
        lines.append("These code changes produced no corresponding plan change:")
        lines.append("")
        for ref in result.unmapped_code_changes:
            lines.append(f"- `{ref}`")
        lines.append("")

    # Footer
    lines.append("---")
    lines.append("*Generated by [tfrev](https://github.com/bishalOps/tfrev)*")

    return "\n".join(lines)


def format_table(result: ReviewResult, config: TfrevConfig) -> str:
    """Format the review result as a colorized terminal table."""
    findings = _filter_findings(result, config)

    verdict_icon = _VERDICT_EMOJI.get(result.verdict, "")
    verdict_style = _VERDICT_STYLE.get(result.verdict, {})
    verdict_text = click.style(result.verdict, **verdict_style)
    confidence_text = click.style(f"{result.confidence:.0%}", bold=True)

    lines = []

    # ── Verdict banner ────────────────────────────────────────────────────────
    rule = click.style("─" * 72, dim=True)
    lines.append(rule)
    lines.append(f"  {verdict_icon}  Verdict: {verdict_text}   Confidence: {confidence_text}")
    lines.append(rule)
    lines.append("")

    # Summary
    lines.append(_wrap(result.summary, indent="  "))
    lines.append("")

    # Resource stats
    s = result.stats
    stats_parts = [
        click.style(str(s.resources_reviewed), bold=True) + " reviewed",
        click.style(f"+{s.resources_created}", fg="green") + " create",
        click.style(f"~{s.resources_updated}", fg="yellow") + " update",
        click.style(f"-{s.resources_deleted}", fg="red") + " delete",
        click.style(f"-/+{s.resources_replaced}", fg="red") + " replace",
    ]
    lines.append("  " + click.style("Resources: ", dim=True) + "  |  ".join(stats_parts))
    lines.append("")

    if not findings:
        lines.append(click.style("  ✓ No findings. Plan looks good!", fg="bright_green", bold=True))
        return "\n".join(lines)

    # ── Summary table ─────────────────────────────────────────────────────────
    lines.append(
        click.style(
            f"  {'ID':<6} {'Severity':<12} {'Category':<20} {'Resource':<36} Title", bold=True
        )
    )
    lines.append(click.style("  " + "─" * 120, dim=True))

    for f in findings:
        sev_label = _sev(f"{f.severity.upper():<12}", f.severity)
        resource = f.resource[-34:] if len(f.resource) > 36 else f.resource
        lines.append(f"  {f.id:<6} {sev_label} {f.category:<20} {resource:<36} {f.title}")

    lines.append("")

    # ── Finding details ───────────────────────────────────────────────────────
    for f in findings:
        sev_icon = _SEVERITY_EMOJI.get(f.severity, "")
        sev_label = _sev(f.severity.upper(), f.severity)
        lines.append(click.style("  " + "─" * 72, dim=True))
        styled_id = click.style(f.id, bold=True)
        styled_title = click.style(f.title, bold=True)
        lines.append(f"  [{styled_id}] {sev_icon} {sev_label} — {styled_title}")
        lines.append("")
        lines.append(_wrap(f.description))

        if f.code_reference:
            file = f.code_reference.get("file", "")
            file_lines = f.code_reference.get("lines", "")
            if file:
                code_label = click.style("Code:", dim=True)
                code_file = click.style(file, fg="cyan")
                lines.append(f"\n  {code_label} {code_file} (lines {file_lines})")

        if f.plan_reference:
            addr = f.plan_reference.get("address", "")
            action = f.plan_reference.get("action", "")
            if addr:
                lines.append(
                    f"  {click.style('Plan:', dim=True)} {click.style(addr, fg='cyan')} ({action})"
                )

        if f.recommendation:
            lines.append("")
            lines.append(f"  {click.style('Recommendation:', bold=True)}")
            lines.append(_wrap(f.recommendation))

        lines.append("")

    lines.append(click.style("  " + "─" * 72, dim=True))

    return "\n".join(lines)


def review_result_from_json(json_str: str) -> ReviewResult:
    """Reconstruct a ReviewResult from tfrev's own JSON output.

    This avoids needing a second API call to get a different output format.
    """
    data = json.loads(json_str)
    review = data.get("review", data)

    findings = []
    for f in review.get("findings", []):
        findings.append(
            Finding(
                id=f.get("id", "F000"),
                severity=f.get("severity", "info"),
                category=f.get("category", "unknown"),
                resource=f.get("resource", "unknown"),
                title=f.get("title", "Untitled"),
                description=f.get("description", ""),
                code_reference=f.get("code_reference"),
                plan_reference=f.get("plan_reference"),
                recommendation=f.get("recommendation", ""),
            )
        )

    stats_raw = review.get("stats", {})
    severity_counts = stats_raw.get("findings_by_severity", {})
    from tfrev.response_parser import ReviewStats

    stats = ReviewStats(
        resources_reviewed=stats_raw.get("resources_reviewed", 0),
        resources_changing=stats_raw.get("resources_changing", 0),
        resources_created=stats_raw.get("resources_created", 0),
        resources_updated=stats_raw.get("resources_updated", 0),
        resources_deleted=stats_raw.get("resources_deleted", 0),
        resources_replaced=stats_raw.get("resources_replaced", 0),
        findings_by_severity={
            "critical": severity_counts.get("critical", 0),
            "high": severity_counts.get("high", 0),
            "medium": severity_counts.get("medium", 0),
            "low": severity_counts.get("low", 0),
            "info": severity_counts.get("info", 0),
        },
    )

    return ReviewResult(
        verdict=review.get("verdict", "WARN"),
        confidence=float(review.get("confidence", 0.5)),
        summary=review.get("summary", ""),
        findings=findings,
        stats=stats,
        unmapped_plan_changes=review.get("unmapped_plan_changes", []),
        unmapped_code_changes=review.get("unmapped_code_changes", []),
    )


def _filter_findings(result: ReviewResult, config: TfrevConfig) -> list[Finding]:
    """Filter findings by severity threshold."""
    return [
        f
        for f in result.findings
        if severity_meets_threshold(f.severity, config.severity_threshold)
    ]
