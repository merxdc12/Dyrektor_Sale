"""URL-only Sheets setup: no credential or private API access."""
import pytest
from pinterest_os.google_sheets_link import parse_sheet_url, public_csv_url

ID = "1-O3W_GesirS5eqKKZTCdAmwKXNS-D_0GpaJN8l8Lito"


def test_google_sheet_link_with_gid():
    url = f"https://docs.google.com/spreadsheets/d/{ID}/edit?usp=sharing#gid=1004"
    assert parse_sheet_url(url) == (ID, "1004")
    assert public_csv_url(url).endswith("format=csv&gid=1004")


@pytest.mark.parametrize("url", [
    "https://evil.example/spreadsheets/d/" + ID + "/edit",
    "http://docs.google.com/spreadsheets/d/" + ID + "/edit",
    "https://docs.google.com.evil.example/spreadsheets/d/" + ID + "/edit",
    "https://docs.google.com/spreadsheets/d/" + ID + "/edit#gid=abc",
    "https://docs.google.com@evil.example/spreadsheets/d/" + ID + "/edit",
])
def test_reject_untrusted_links(url):
    with pytest.raises(ValueError):
        parse_sheet_url(url)
