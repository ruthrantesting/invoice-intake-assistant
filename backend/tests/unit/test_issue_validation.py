from decimal import Decimal

import pytest

from invoice_agent.domain.duplicate_validation import DuplicateCandidate, find_duplicate_matches
from invoice_agent.domain.issue_validation import run_issue_checks


def test_missing_identifiers_never_match_and_exact_hash_matches() -> None:
    candidates = [
        DuplicateCandidate("same", None, None, "abc"),
        DuplicateCandidate("missing", None, None, None),
    ]
    matches = find_duplicate_matches(
        invoice_number=None,
        vendor=None,
        source_sha256="abc",
        candidates=candidates,
        scope="selected workbook v1",
    )
    assert [match.record_id for match in matches] == ["same"]
    assert matches[0].scope == "selected workbook v1"


def test_duplicate_identifier_match_is_explained() -> None:
    matches = find_duplicate_matches(
        invoice_number="INV-001",
        vendor="Acme Ltd.",
        source_sha256=None,
        candidates=[DuplicateCandidate("record-1", "inv 001", "ACME LTD", None)],
        scope="tenant records",
    )
    assert matches[0].reason == "Normalized invoice number and vendor match."


def test_exact_file_hash_duplicate_is_reported_with_scope() -> None:
    matches = find_duplicate_matches(
        invoice_number=None,
        vendor=None,
        source_sha256="ab" * 32,
        candidates=[DuplicateCandidate("source-record", None, None, "ab" * 32)],
        scope="selected workbook v3",
    )
    assert len(matches) == 1
    assert matches[0].record_id == "source-record"
    assert "Exact source" in matches[0].reason
    assert matches[0].scope == "selected workbook v3"


def test_issue_checks_flag_missing_po_and_surface_duplicate_scope() -> None:
    results = run_issue_checks(
        subtotal=Decimal("10"),
        tax=Decimal("1"),
        other_charges=Decimal("0"),
        discounts=Decimal("0"),
        total=Decimal("11"),
        tolerance=Decimal("0.01"),
        po_number=None,
        invoice_number="INV-1",
        vendor="Acme",
        source_sha256=None,
        candidates=[DuplicateCandidate("record-1", "INV1", "ACME", None)],
        comparison_scope="selected workbook version 2",
    )
    assert (
        next(result for result in results if result.check_type == "missing_po").outcome == "flagged"
    )
    duplicate = next(result for result in results if result.check_type == "duplicate")
    assert duplicate.outcome == "flagged"
    assert duplicate.comparison_scope == "selected workbook version 2"


def test_currency_tolerance_is_not_assumed_when_configuration_missing(monkeypatch) -> None:
    from pydantic import ValidationError

    from invoice_agent.config import Settings

    with pytest.raises(ValidationError):
        Settings(currency_tolerances_json="not-json")


def test_default_settings_fail_closed_for_production_readiness() -> None:
    from invoice_agent.config import Settings

    settings = Settings()
    issues = settings.production_readiness_issues()
    assert issues
    assert any("provider" in issue.lower() for issue in issues)
    assert any("oidc" in issue.lower() for issue in issues)
