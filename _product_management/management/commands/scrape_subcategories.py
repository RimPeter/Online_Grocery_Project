"""
python manage.py scrape_subcategories

Scrape subcategories from Bestway main category pages listed in main_urls.json.

Usage:
    python manage.py scrape_subcategories

This command:
  - Reads a list of main-category paths from main_urls.json
  - Fetches each category page from https://www.bestwaywholesale.co.uk
  - Looks for <ul class="caps chevron"> lists containing subcategory links
  - Writes the collected structure to subcategories.json next to this file

Resulting JSON structure (example):
{
  "Bread & Cakes": {
    "Bread & Morning Goods": "https://www.bestwaywholesale.co.uk/bread-cakes/401",
    "Cakes": "https://www.bestwaywholesale.co.uk/bread-cakes/381"
  },
  "Fresh Foods": {
    "Bacon": "https://www.bestwaywholesale.co.uk/chilled-fresh/501"
  }
}
"""

import json
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.core.management.base import BaseCommand


BASE_URL = "https://www.bestwaywholesale.co.uk"

# Simple browser-like headers to reduce blocking
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Connection": "close",
}


class Command(BaseCommand):
    help = (
        "Scrape Bestway main category pages from main_urls.json and "
        "write discovered subcategories to subcategories.json."
    )

    def add_arguments(self, parser):
        script_dir = Path(__file__).resolve().parent

        parser.add_argument(
            "--input",
            type=str,
            default=str(script_dir / "main_urls.json"),
            help="Path to main_urls.json (default: commands/main_urls.json).",
        )
        parser.add_argument(
            "--output",
            type=str,
            default=str(script_dir / "subcategories.json"),
            help="Path to write subcategories.json "
                 "(default: commands/subcategories.json).",
        )
        parser.add_argument(
            "--base-url",
            type=str,
            default=BASE_URL,
            help="Base site URL (default: https://www.bestwaywholesale.co.uk).",
        )

    def handle(self, *args, **options):
        input_path = Path(options["input"])
        output_path = Path(options["output"])
        base_url = options["base_url"].rstrip("/")

        if not input_path.exists():
            raise SystemExit(
                f"Input file not found: {input_path}. "
                "Ensure main_urls.json exists next to this command."
            )

        with input_path.open(encoding="utf-8") as fh:
            try:
                main_paths = json.load(fh)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"Failed to parse {input_path}: {exc}") from exc

        if not isinstance(main_paths, list):
            raise SystemExit(
                f"Expected a JSON list in {input_path}, got {type(main_paths).__name__}"
            )

        session = requests.Session()
        session.headers.update(HEADERS)

        all_data = {}
        total_subcats = 0

        for raw_path in main_paths:
            if not isinstance(raw_path, str):
                self.stdout.write(
                    self.style.WARNING(f"Skipping non-string path: {raw_path!r}")
                )
                continue

            path = raw_path.strip().lstrip("/")
            if not path:
                continue

            url = f"{base_url}/{path}"
            self.stdout.write(self.style.NOTICE(f"Fetching: {url}"))

            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as exc:
                self.stderr.write(self.style.WARNING(f"  Skipped ({exc})"))
                continue

            soup = BeautifulSoup(resp.text, "html.parser")

            # Try to detect a human-friendly main category label from the breadcrumb
            main_label = self._extract_main_label(soup) or path

            subcats_for_main = all_data.setdefault(main_label, {})
            count_before = len(subcats_for_main)

            # Subcategories are expected in <ul class="caps chevron"> lists
            uls = soup.select("ul.caps.chevron")
            if not uls:
                self.stderr.write(
                    self.style.WARNING("  No <ul class='caps chevron'> found on page.")
                )

            for ul in uls:
                for li in ul.find_all("li"):
                    a = li.find("a")
                    if not a or not a.get("href"):
                        continue

                    name = " ".join(a.get_text(" ", strip=True).split())
                    href = a.get("href", "").strip()
                    if not href:
                        continue

                    if href.startswith("http://") or href.startswith("https://"):
                        full_url = href
                    else:
                        full_url = f"{base_url}{href}"

                    existing = subcats_for_main.get(name)
                    if existing is None:
                        subcats_for_main[name] = full_url
                    else:
                        # If multiple URLs exist for the same subcategory,
                        # store them as a list (mirrors product_category.json style).
                        if isinstance(existing, list):
                            if full_url not in existing:
                                existing.append(full_url)
                        else:
                            if full_url != existing:
                                subcats_for_main[name] = [existing, full_url]

            added = len(subcats_for_main) - count_before
            total_subcats += max(0, added)
            self.stdout.write(f"  Found {added} new subcategories for {main_label!r}")

        # Write the collected data to JSON
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as fh:
            json.dump(all_data, fh, ensure_ascii=False, indent=2)
        tmp_path.replace(output_path)

        self.stdout.write(
            self.style.SUCCESS(
                f"\nWrote {total_subcats} subcategories across "
                f"{len(all_data)} main categories to {output_path}"
            )
        )

    @staticmethod
    def _extract_main_label(soup):
        """
        Try to extract a human-readable main category label.

        The breadcrumb structure on Bestway pages typically looks like:
            <div class="prodnav ...">
              <ul class="breadcrumb">
                <li><a href="/bread-cakes">Bread &amp; Cakes</a></li>
              </ul>
            </div>
        """
        crumb_link = soup.select_one(".prodnav ul.breadcrumb li a")
        if crumb_link:
            text = crumb_link.get_text(" ", strip=True)
            return " ".join(text.split())
        return None

