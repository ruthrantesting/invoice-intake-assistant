from dataclasses import dataclass


@dataclass(frozen=True)
class DuplicateCandidate:
    record_id: str
    invoice_number: str | None
    vendor: str | None
    source_sha256: str | None


@dataclass(frozen=True)
class DuplicateMatch:
    record_id: str
    reason: str
    scope: str


def normalize_identifier(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = "".join(character for character in value.casefold() if character.isalnum())
    return normalized or None


def find_duplicate_matches(
    *,
    invoice_number: str | None,
    vendor: str | None,
    source_sha256: str | None,
    candidates: list[DuplicateCandidate],
    scope: str,
) -> list[DuplicateMatch]:
    invoice_key = normalize_identifier(invoice_number)
    vendor_key = normalize_identifier(vendor)
    matches: list[DuplicateMatch] = []
    for candidate in candidates:
        if source_sha256 and candidate.source_sha256 == source_sha256:
            matches.append(DuplicateMatch(candidate.record_id, "Exact source file match.", scope))
            continue
        candidate_invoice = normalize_identifier(candidate.invoice_number)
        candidate_vendor = normalize_identifier(candidate.vendor)
        if (
            invoice_key
            and candidate_invoice
            and invoice_key == candidate_invoice
            and vendor_key
            and candidate_vendor
            and vendor_key == candidate_vendor
        ):
            reason = "Normalized invoice number and vendor match."
            matches.append(DuplicateMatch(candidate.record_id, reason, scope))
    return matches
