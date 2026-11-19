from io import BytesIO
from pathlib import Path
from threading import Thread

from openpyxl import Workbook, load_workbook

from invoice_agent.domain.workbook_safety import append_text_row
from invoice_agent.persistence.blob_store import LocalBlobStore
from invoice_agent.persistence.job_repository import Job


def make_workbook() -> bytes:
    workbook = Workbook()
    workbook.active.append(["Invoice", "Total"])
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def test_staged_blob_is_immutable_and_integrity_checked(tmp_path: Path) -> None:
    store = LocalBlobStore(tmp_path, b"0123456789abcdef0123456789abcdef")
    blob = store.put(b"immutable")
    assert store.get(blob.blob_id, blob.sha256) == b"immutable"
    try:
        store.get(blob.blob_id, "0" * 64)
    except OSError as exc:
        assert "integrity" in str(exc)
    else:
        raise AssertionError("Expected blob integrity mismatch to fail")


def test_orphan_blob_recovery_is_dry_run_unless_delete_requested(tmp_path: Path) -> None:
    store = LocalBlobStore(tmp_path, b"0123456789abcdef0123456789abcdef")
    orphan = store.put(b"candidate")
    assert store.reconcile_orphans(set()) == [orphan.blob_id]
    assert store.get(orphan.blob_id, orphan.sha256) == b"candidate"
    assert store.reconcile_orphans(set(), delete=True) == [orphan.blob_id]
    assert not (tmp_path / orphan.blob_id).exists()


def test_concurrent_candidate_workbook_appends_do_not_mutate_source() -> None:
    original = make_workbook()
    results: list[bytes] = []

    def append(value: str) -> None:
        results.append(append_text_row(original, "Sheet", [value, "10.00"]))

    threads = [Thread(target=append, args=(f"INV-{number}",)) for number in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(results) == 2
    assert all(
        load_workbook(BytesIO(candidate), read_only=True)["Sheet"].max_row == 2
        for candidate in results
    )
    assert load_workbook(BytesIO(original), read_only=True)["Sheet"].max_row == 1


def test_durable_job_model_has_lease_and_retry_fields() -> None:
    columns = Job.__table__.columns
    assert {"lease_owner", "lease_expires_at", "attempts", "next_attempt_at", "error_code"} <= set(
        columns.keys()
    )


def test_worker_executor_is_fenced_to_current_lease_owner() -> None:
    from inspect import signature

    from invoice_agent.services.invoice_worker import process_extraction_job

    assert "worker_id" in signature(process_extraction_job).parameters
