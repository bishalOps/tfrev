"""Tests for tfrev.output."""

from __future__ import annotations

import json

import pytest

from tfrev.client import APIResponse
from tfrev.config import TfrevConfig
from tfrev.output import format_json, format_markdown, format_table, review_result_from_json
from tfrev.response_parser import Finding, ReviewResult, ReviewStats


@pytest.fixture
def sample_result():
    return ReviewResult(
        verdict="FAIL",
        confidence=0.92,
        summary="Security regression detected.",
        findings=[
            Finding(
                id="F001",
                severity="critical",
                category="security",
                resource="aws_security_group.web",
                title="SSH open to internet",
                description="Ingress widened to 0.0.0.0/0",
                code_reference={"file": "main.tf", "lines": "10-15"},
                plan_reference={"action": "update", "address": "aws_security_group.web"},
                recommendation="Restrict CIDR range.",
            ),
            Finding(
                id="F002",
                severity="low",
                category="best_practice",
                resource="aws_instance.web",
                title="Missing tags",
                description="No standard tags found.",
                recommendation="Add tags.",
            ),
        ],
        stats=ReviewStats(
            resources_reviewed=3,
            resources_changing=2,
            resources_created=1,
            resources_updated=1,
            resources_deleted=0,
            resources_replaced=0,
            findings_by_severity={
                "critical": 1,
                "high": 0,
                "medium": 0,
                "low": 1,
                "info": 0,
            },
        ),
        unmapped_plan_changes=["aws_route53_record.drift"],
        unmapped_code_changes=["outputs.tf"],
    )


@pytest.fixture
def pass_result_simple():
    return ReviewResult(
        verdict="PASS",
        confidence=0.95,
        summary="All changes match intent.",
        findings=[],
        stats=ReviewStats(resources_reviewed=1, resources_changing=1, resources_created=1),
    )


class TestFormatJson:
    def test_valid_json(self, sample_result, default_config):
        output = format_json(sample_result, default_config)
        data = json.loads(output)
        assert "review" in data

    def test_verdict(self, sample_result, default_config):
        output = format_json(sample_result, default_config)
        data = json.loads(output)
        assert data["review"]["verdict"] == "FAIL"

    def test_findings_count(self, sample_result, default_config):
        output = format_json(sample_result, default_config)
        data = json.loads(output)
        assert len(data["review"]["findings"]) == 2

    def test_severity_filter(self, sample_result):
        config = TfrevConfig(severity_threshold="high")
        output = format_json(sample_result, config)
        data = json.loads(output)
        # Only critical finding should remain (low is below high threshold)
        assert len(data["review"]["findings"]) == 1
        assert data["review"]["findings"][0]["severity"] == "critical"

    def test_stats(self, sample_result, default_config):
        output = format_json(sample_result, default_config)
        data = json.loads(output)
        assert data["review"]["stats"]["resources_reviewed"] == 3

    def test_unmapped(self, sample_result, default_config):
        output = format_json(sample_result, default_config)
        data = json.loads(output)
        assert "aws_route53_record.drift" in data["review"]["unmapped_plan_changes"]


class TestFormatMarkdown:
    def test_contains_verdict(self, sample_result, default_config):
        output = format_markdown(sample_result, default_config)
        assert "FAIL" in output

    def test_contains_findings(self, sample_result, default_config):
        output = format_markdown(sample_result, default_config)
        assert "SSH open to internet" in output
        assert "CRITICAL" in output

    def test_contains_summary(self, sample_result, default_config):
        output = format_markdown(sample_result, default_config)
        assert "Security regression" in output

    def test_contains_stats(self, sample_result, default_config):
        output = format_markdown(sample_result, default_config)
        assert "3 reviewed" in output

    def test_unmapped_sections(self, sample_result, default_config):
        output = format_markdown(sample_result, default_config)
        assert "Unmapped Plan Changes" in output
        assert "aws_route53_record.drift" in output

    def test_pass_no_findings(self, pass_result_simple, default_config):
        output = format_markdown(pass_result_simple, default_config)
        assert "PASS" in output
        assert "No findings" in output

    def test_severity_filter(self, sample_result):
        config = TfrevConfig(severity_threshold="high")
        output = format_markdown(sample_result, config)
        assert "SSH open to internet" in output
        assert "Missing tags" not in output

    def test_footer_without_metadata(self, sample_result, default_config):
        output = format_markdown(sample_result, default_config)
        assert "tfrev" in output
        assert "tokens" not in output

    def test_footer_with_metadata(self, sample_result, default_config):
        response = APIResponse(
            content="",
            model="claude-sonnet-4-6",
            input_tokens=1847,
            output_tokens=412,
            stop_reason="end_turn",
        )
        output = format_markdown(sample_result, default_config, response, 3.2)
        assert "1,847 tokens in" in output
        assert "412 out" in output
        assert "3.2s" in output
        assert "claude-sonnet-4-6" in output
        assert "anthropic" in output


class TestReviewResultFromJson:
    def test_roundtrip(self, sample_result, default_config):
        """JSON output can be reconstructed back into a ReviewResult."""
        json_str = format_json(sample_result, default_config)
        reconstructed = review_result_from_json(json_str)
        assert reconstructed.verdict == sample_result.verdict
        assert reconstructed.confidence == sample_result.confidence
        assert len(reconstructed.findings) == len(sample_result.findings)
        assert reconstructed.findings[0].id == sample_result.findings[0].id
        assert reconstructed.stats.resources_reviewed == sample_result.stats.resources_reviewed

    def test_roundtrip_markdown(self, sample_result, default_config):
        """JSON -> ReviewResult -> Markdown produces valid output."""
        json_str = format_json(sample_result, default_config)
        reconstructed = review_result_from_json(json_str)
        md = format_markdown(reconstructed, default_config)
        assert "FAIL" in md
        assert "SSH open to internet" in md

    def test_pass_result(self, pass_result_simple, default_config):
        json_str = format_json(pass_result_simple, default_config)
        reconstructed = review_result_from_json(json_str)
        assert reconstructed.verdict == "PASS"
        assert len(reconstructed.findings) == 0


class TestFormatTable:
    def test_contains_verdict(self, sample_result, default_config):
        output = format_table(sample_result, default_config)
        assert "FAIL" in output

    def test_contains_finding_ids(self, sample_result, default_config):
        output = format_table(sample_result, default_config)
        assert "F001" in output
        assert "F002" in output

    def test_pass_message(self, pass_result_simple, default_config):
        output = format_table(pass_result_simple, default_config)
        assert "No findings" in output

    def test_severity_filter(self, sample_result):
        config = TfrevConfig(severity_threshold="high")
        output = format_table(sample_result, config)
        assert "F001" in output
        assert "F002" not in output

    def test_footer_without_metadata(self, sample_result, default_config):
        output = format_table(sample_result, default_config)
        assert "tokens" not in output

    def test_footer_with_metadata(self, sample_result, default_config):
        response = APIResponse(
            content="",
            model="claude-sonnet-4-6",
            input_tokens=1847,
            output_tokens=412,
            stop_reason="end_turn",
        )
        output = format_table(sample_result, default_config, response, 3.2)
        assert "1,847 tokens in" in output
        assert "412 out" in output
        assert "3.2s" in output
        assert "claude-sonnet-4-6" in output
        assert "anthropic" in output

    def test_footer_with_metadata_no_findings(self, pass_result_simple, default_config):
        response = APIResponse(
            content="",
            model="claude-sonnet-4-6",
            input_tokens=500,
            output_tokens=100,
            stop_reason="end_turn",
        )
        output = format_table(pass_result_simple, default_config, response, 1.5)
        assert "500 tokens in" in output
        assert "1.5s" in output
