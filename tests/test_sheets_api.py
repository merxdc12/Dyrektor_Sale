"""Offline tests for Google Sheets safety boundaries; no Google credentials needed."""
import pytest
from pinterest_os.sheets_api import _range, safe_cell


@pytest.mark.parametrize("text", ["=SUM(1,1)", "+1", "-2", "@SUM(A1)", "  =IMPORTXML(1)"])
def test_formula_like_values_are_escaped(text):
    assert safe_cell(text).startswith("'")


def test_safe_text_and_null():
    assert safe_cell("plain text") == "plain text"
    assert safe_cell(None) == ""


def test_worksheet_range_escapes_quotes():
    assert _range("O'Brien") == "'O''Brien'"


@pytest.mark.parametrize("title", ["", "x/y", "a:b", "x" * 101])
def test_invalid_worksheet_title(title):
    with pytest.raises(ValueError):
        _range(title)
