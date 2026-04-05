"""Shared test fixtures for tfrev."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tfrev.config import TfrevConfig
from tfrev.diff_parser import DiffSummary, parse_diff
from tfrev.plan_parser import PlanSummary, parse_plan_json
from tfrev.response_parser import ReviewResult, parse_response

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


# --- Plan fixtures ---


@pytest.fixture
def minimal_plan_json() -> dict:
    return json.loads((FIXTURES_DIR / "plan_minimal.json").read_text())


@pytest.fixture
def complex_plan_json() -> dict:
    return json.loads((FIXTURES_DIR / "plan_complex.json").read_text())


@pytest.fixture
def sensitive_plan_json() -> dict:
    return json.loads((FIXTURES_DIR / "plan_sensitive.json").read_text())


@pytest.fixture
def empty_plan_json() -> dict:
    return json.loads((FIXTURES_DIR / "plan_empty.json").read_text())


@pytest.fixture
def minimal_plan(minimal_plan_json: dict) -> PlanSummary:
    return parse_plan_json(minimal_plan_json)


@pytest.fixture
def complex_plan(complex_plan_json: dict) -> PlanSummary:
    return parse_plan_json(complex_plan_json)


# --- Diff fixtures ---


@pytest.fixture
def simple_diff_text() -> str:
    return (FIXTURES_DIR / "diff_simple.diff").read_text()


@pytest.fixture
def multifile_diff_text() -> str:
    return (FIXTURES_DIR / "diff_multifile.diff").read_text()


@pytest.fixture
def empty_diff_text() -> str:
    return (FIXTURES_DIR / "diff_empty.diff").read_text()


@pytest.fixture
def simple_diff(simple_diff_text: str) -> DiffSummary:
    return parse_diff(simple_diff_text)


@pytest.fixture
def multifile_diff(multifile_diff_text: str) -> DiffSummary:
    return parse_diff(multifile_diff_text)


# --- Response fixtures ---


@pytest.fixture
def pass_response_text() -> str:
    return (FIXTURES_DIR / "response_pass.json").read_text()


@pytest.fixture
def fail_response_text() -> str:
    return (FIXTURES_DIR / "response_fail.json").read_text()


@pytest.fixture
def malformed_response_text() -> str:
    return (FIXTURES_DIR / "response_malformed.txt").read_text()


@pytest.fixture
def fenced_response_text() -> str:
    return (FIXTURES_DIR / "response_fenced.txt").read_text()


@pytest.fixture
def pass_result(pass_response_text: str) -> ReviewResult:
    return parse_response(pass_response_text)


@pytest.fixture
def fail_result(fail_response_text: str) -> ReviewResult:
    return parse_response(fail_response_text)


# --- Config fixtures ---


@pytest.fixture
def default_config() -> TfrevConfig:
    return TfrevConfig()


@pytest.fixture
def full_config_path() -> Path:
    return FIXTURES_DIR / "config_full.yaml"
