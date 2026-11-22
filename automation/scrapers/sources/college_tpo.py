
"""
College & TPO public directory scraper (BE-31).

Extracts publicly available college placement and TPO listings.
Uses HTML fixtures for offline parser testing.
"""

import logging
import re
from html.parser import HTMLParser
from typing import Any, Dict, List
from urllib.parse import urljoin

import requests

from automation.scrapers.base import (
    BaseScraper,
    AccessDeniedError,
    RateLimitedError,
    NetworkTimeoutError,
)
from automation.scrapers.registry import register_scraper

logger = logging.getLogger(__name__)


class CollegeTPOHTMLParser(HTMLParser):
    """Extracts college/TPO listing cards from public directory HTML."""

    CARD_CLASSES = {
        "college-tpo-card",
        "college-listing",
        "tpo-listing",
    }

    FIELD_NAMES = {
        "company",
        "college",
        "title",
        "description",
        "experience",
        "salary",
        "stipend",
        "location",
        "url",
    }

    def __init__(self):
        super().__init__()
        self.records = []
        self.current = None
        self.current_field = None
        self.current_text = []
        self.card_tag = None
        self.card_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set((attrs.get("class") or "").split())

        if self.current is None and (
            tag in ("article", "li")
            or classes.intersection(self.CARD_CLASSES)
        ):
            self.current = {}
            self.card_tag = tag
            self.card_depth = 1
        elif self.current is not None and tag == self.card_tag:
            self.card_depth += 1

        field = attrs.get("data-field")

        if field not in self.FIELD_NAMES:
            field = next(
                (name for name in self.FIELD_NAMES if name in classes),
                None,
            )

        if self.current is not None and field:
            self.current_field = field
            self.current_text = []

        if self.current is not None and tag == "a":
            href = attrs.get("href")
            if href and not self.current.get("url"):
                self.current["url"] = href

    def handle_data(self, data):
        if self.current is not None and self.current_field:
            self.current_text.append(data.strip())

    def handle_endtag(self, tag):
        if self.current is None:
            return

        if self.current_field and tag in ("div", "span", "p", "h2", "h3", "a"):
            value = " ".join(
                part for part in self.current_text if part
            )

            if value:
                self.current.setdefault(self.current_field, value)

            self.current_field = None
            self.current_text = []

        if tag == self.card_tag:
            self.card_depth -= 1

            if self.card_depth == 0:
                if self.current:
                    self.records.append(self.current)

                self.current = None
                self.card_tag = None


class CollegeTPOScraper(BaseScraper):
    """Scraper for public college placement and TPO directories."""

    def fetch(self, url: str) -> str:
        try:
            response = requests.get(
                url,
                timeout=15,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; PublicDirectoryBot/1.0)"
                },
            )
        except requests.Timeout as exc:
            raise NetworkTimeoutError(str(exc)) from exc
        except requests.RequestException as exc:
            raise NetworkTimeoutError(str(exc)) from exc

        if response.status_code == 403:
            raise AccessDeniedError(
                "Access denied by source (HTTP 403)"
            )

        if response.status_code == 429:
            raise RateLimitedError(
                "Rate limited by source (HTTP 429)"
            )

        response.raise_for_status()
        return response.text

    def parse(self, content: str) -> List[Dict[str, Any]]:
        parser = CollegeTPOHTMLParser()
        parser.feed(content)

        results = []

        for item in parser.records:
            company = item.get("company") or item.get("college")
            title = item.get("title")
            source_url = item.get("url")

            if not company or not title or not source_url:
                continue

            source_url = urljoin(self.base_url, source_url)

            experience = item.get("experience", "")
            match = re.search(
                r"(\d+)\s*(?:-|to)\s*(\d+)",
                experience,
                re.I,
            )

            experience_min = int(match.group(1)) if match else None
            experience_max = int(match.group(2)) if match else None

            results.append({
                "type": "college",
                "company": company,
                "title": title,
                "description": item.get("description"),
                "experience_min": experience_min,
                "experience_max": experience_max,
                "salary_text": item.get("salary") or item.get("stipend"),
                "location": item.get("location"),
                "source_url": source_url,
                "source_id": self.source_id,
                "source_identifier": source_url,
            })

        return results


register_scraper("college_tpo", CollegeTPOScraper)
