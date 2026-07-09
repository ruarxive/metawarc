import pytest

from metawarc.dbutil import build_record_filter, validate_where_clause


def test_validate_where_clause_allows_simple_filters():
    assert validate_where_clause("ext = 'pdf'") == "ext = 'pdf'"


def test_validate_where_clause_rejects_injection():
    with pytest.raises(ValueError):
        validate_where_clause("1=1; DROP TABLE files")


def test_build_record_filter_mimes():
    clause = build_record_filter(mimes="text/html,application/pdf")
    assert "c_type in ('text/html','application/pdf')" in clause


def test_build_record_filter_url_pattern():
    clause = build_record_filter(url_pattern="example.com")
    assert "url like '%example.com%'" in clause
