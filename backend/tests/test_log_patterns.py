from app.collectors.log_pattern_collector import (
    group_loki_error_signatures,
    signature_for_log_line,
)


def test_signature_extraction_normalizes_repeated_messages() -> None:
    assert (
        signature_for_log_line("ERROR checkout failed for order 123 after 5.5 seconds")
        == "error checkout failed for order <num> after <num> seconds"
    )


def test_loki_streams_group_top_error_signatures_with_first_and_last_seen() -> None:
    result = [
        {
            "stream": {"namespace": "payments", "pod": "checkout-api-7d9f"},
            "values": [
                ["1777651200000000000", "ERROR checkout failed for order 123"],
                ["1777651260000000000", "error checkout failed for order 456"],
                ["1777651320000000000", "connection refused to db host 10.0.0.1"],
                ["1777651380000000000", "request completed"],
            ],
        }
    ]

    grouped = group_loki_error_signatures(result)
    signatures = grouped[("payments", "checkout-api-7d9f")]

    assert signatures[0].signature == "error checkout failed for order <num>"
    assert signatures[0].count == 2
    assert signatures[0].first_seen.isoformat() == "2026-05-01T16:00:00+00:00"
    assert signatures[0].last_seen.isoformat() == "2026-05-01T16:01:00+00:00"
    assert signatures[1].signature == "connection refused to db host <num>.<num>"
