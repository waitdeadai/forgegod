"""Existing tests that benchmark tasks must NOT break."""

from utils import format_output, process_data


def test_filter_positive():
    data = [{"value": 5}, {"value": -1}, {"value": 3}]
    result = process_data(data, "filter")
    assert result == [5, 3]


def test_transform_strings():
    data = ["hello", " World "]
    result = process_data(data, "transform")
    assert result == ["HELLO", "WORLD"]


def test_aggregate():
    data = [10, 20, 30]
    result = process_data(data, "aggregate")
    assert result == [{"total": 60, "count": 3, "average": 20.0}]


def test_validate_email():
    data = [
        {"name": "Alice", "email": "alice@example.com"},
        {"name": "Bob"},
        {"email": "no-name@test.com"},
    ]
    result = process_data(data, "validate")
    assert len(result) == 1
    assert result[0]["name"] == "Alice"


def test_format_text():
    data = [{"a": 1, "b": 2}]
    result = format_output(data, "text")
    assert "a=1" in result
    assert "b=2" in result


def test_format_csv():
    data = [{"name": "Alice", "age": 30}]
    result = format_output(data, "csv")
    assert "name,age" in result
    assert "Alice,30" in result
