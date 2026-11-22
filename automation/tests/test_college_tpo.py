
import pytest
from pathlib import Path

from automation.scrapers.base import AccessDeniedError, RateLimitedError
from automation.scrapers.sources.college_tpo import CollegeTPOScraper


FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "college_tpo.html"
)


def test_college_tpo_parses_fixture():
    html = FIXTURE_PATH.read_text(encoding="utf-8")

    scraper = CollegeTPOScraper(
        source_id="college_tpo",
        base_url="https://colleges.example.edu",
    )

    results = scraper.parse(html)

    assert len(results) == 1

    record = results[0]

    assert record["type"] == "college"
    assert record["company"] == "National Engineering Institute"
    assert record["title"] == "2026 Campus Placement Drive"
    assert record["experience_min"] == 0
    assert record["experience_max"] == 1
    assert record["salary_text"] == "₹5,00,000 - ₹7,00,000 PA"
    assert record["location"] == "Pune, India"
    assert record["source_id"] == "college_tpo"
    assert record["source_url"] == (
        "https://colleges.example.edu/placements/2026"
    )


def test_college_tpo_skips_incomplete_records():
    html = """
    <article class="college-tpo-card">
        <h2 class="company">Test College</h2>
    </article>
    """

    scraper = CollegeTPOScraper(
        source_id="college_tpo",
        base_url="https://colleges.example.edu",
    )

    assert scraper.parse(html) == []


def test_fetch_stops_on_http_403(monkeypatch):
    scraper = CollegeTPOScraper(
        source_id="college_tpo",
        base_url="https://colleges.example.edu",
    )

    class FakeResponse:
        status_code = 403

    monkeypatch.setattr(
        "automation.scrapers.sources.college_tpo.requests.get",
        lambda *args, **kwargs: FakeResponse(),
    )

    with pytest.raises(AccessDeniedError):
        scraper.fetch("https://colleges.example.edu")


def test_fetch_stops_on_http_429(monkeypatch):
    scraper = CollegeTPOScraper(
        source_id="college_tpo",
        base_url="https://colleges.example.edu",
    )

    class FakeResponse:
        status_code = 429

    monkeypatch.setattr(
        "automation.scrapers.sources.college_tpo.requests.get",
        lambda *args, **kwargs: FakeResponse(),
    )

    with pytest.raises(RateLimitedError):
        scraper.fetch("https://colleges.example.edu")


def test_college_tpo_parses_multiple_div_cards():
    html = """
    <div class="college-tpo-card">
        <h2 class="company">College One</h2>
        <h3 class="title">Python Placement</h3>
        <a href="/one">Details</a>
    </div>
    <div class="college-tpo-card">
        <h2 class="company">College Two</h2>
        <h3 class="title">Data Science Placement</h3>
        <a href="/two">Details</a>
    </div>
    """

    scraper = CollegeTPOScraper(
        source_id="college_tpo",
        base_url="https://colleges.example.edu",
    )

    results = scraper.parse(html)

    assert len(results) == 2
    assert results[0]["company"] == "College One"
    assert results[1]["company"] == "College Two"
