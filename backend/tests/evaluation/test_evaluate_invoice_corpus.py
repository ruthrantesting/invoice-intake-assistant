from evaluation.evaluate_invoice_corpus import score


def test_score_reports_accuracy_correction_share_and_duplicate_metrics() -> None:
    report = score(
        [
            {
                "format": "pdf",
                "quality": "clean",
                "expected": {"invoice_number": "00042", "total": "10.00"},
                "predicted": {"invoice_number": "00042", "total": "10.00"},
                "expected_duplicate": True,
                "predicted_duplicate": True,
                "latency_ms": 100,
            },
            {
                "format": "heic",
                "quality": "blurred",
                "expected": {"invoice_number": "A-1"},
                "predicted": {"invoice_number": None},
                "expected_duplicate": False,
                "predicted_duplicate": True,
                "latency_ms": 200,
            },
        ]
    )
    assert report["field_accuracy_by_format_quality"]["pdf/clean"]["accuracy"] == 1
    assert report["field_accuracy_by_format_quality"]["heic/blurred"]["accuracy"] == 0
    assert report["correction_share"] == 1 / 3
    assert report["duplicate_precision"] == 0.5
    assert report["duplicate_recall"] == 1
    assert report["latency_ms"]["median"] == 150
    assert report["latency_ms"]["p95"] == 200
    assert report["latency_ms"]["median"] == 150
    assert report["latency_ms"]["p95"] == 200
