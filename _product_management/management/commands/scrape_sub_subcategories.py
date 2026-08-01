"""
Scrape sub-subcategories from Bestway subcategory pages listed in subcategories.json.

Usage:
    python manage.py scrape_sub_subcategories

This command:
  - Reads nested categories from subcategories.json produced by scrape_subcategories
  - For each subcategory URL, fetches the page
  - Looks for <ul class="caps chevron"> lists containing deeper links
  - Writes the collected structure to sub_subcategories.json next to this file

Resulting JSON structure (example):
{
  "Grocery": {
    "Biscuits": {
      "Chocolate Biscuits": "https://www.bestwaywholesale.co.uk/grocery/11/503001",
      "Luxury Biscuits": "https://www.bestwaywholesale.co.uk/grocery/11/503002"
    },
    "Cereals": {
      "Children's Cereals": "https://www.bestwaywholesale.co.uk/grocery/21/503101"
    }
  }
}
If a sub-subcategory has multiple distinct URLs, the value is a list of URLs.
"""

import json
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand, CommandError

from .scraper_for_sub_subcategory import Command as ProductScraperCommand


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
        "Scrape Bestway subcategory pages from subcategories.json and "
        "write discovered sub-subcategories to sub_subcategories.json."
    )

    def add_arguments(self, parser):
        script_dir = Path(__file__).resolve().parent

        parser.add_argument(
            "--input",
            type=str,
            default=str(script_dir / "subcategories.json"),
            help="Path to subcategories.json (default: commands/subcategories.json).",
        )
        parser.add_argument(
            "--output",
            type=str,
            default=str(script_dir / "sub_subcategories.json"),
            help="Path to write sub_subcategories.json "
                 "(default: commands/sub_subcategories.json).",
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
                "Ensure subcategories.json exists (run scrape_subcategories first)."
            )

        with input_path.open(encoding="utf-8") as fh:
            try:
                categories = json.load(fh)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"Failed to parse {input_path}: {exc}") from exc

        if not isinstance(categories, dict):
            raise SystemExit(
                f"Expected a JSON object in {input_path}, got {type(categories).__name__}"
            )

        session = requests.Session()
        session.headers.update(HEADERS)
        request_attempts = 0
        request_failures = 0

        result: dict = {}
        total_sub_subcats = 0
        pagination_cache = {}

        for main_cat, subcat_map in categories.items():
            if not isinstance(subcat_map, dict):
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipping non-dict subcategories for main category {main_cat!r}"
                    )
                )
                continue

            main_bucket = result.setdefault(main_cat, {})

            for subcat_name, value in subcat_map.items():
                urls = self._normalize_to_list(value)
                if not urls:
                    continue

                sub_bucket = main_bucket.setdefault(subcat_name, {})
                before = len(sub_bucket)

                for url in urls:
                    if not isinstance(url, str):
                        self.stdout.write(
                            self.style.WARNING(
                                f"Skipping non-string URL for {main_cat!r} -> "
                                f"{subcat_name!r}: {url!r}"
                            )
                        )
                        continue

                    page_url = url.strip()
                    if not page_url:
                        continue

                    # If somehow the URL is relative, make it absolute
                    if not page_url.startswith("http://") and not page_url.startswith("https://"):
                        if not page_url.startswith("/"):
                            page_url = "/" + page_url
                        page_url = f"{base_url}{page_url}"

                    self.stdout.write(
                        self.style.NOTICE(
                            f"Fetching subcategory page: {page_url} "
                            f"({main_cat} -> {subcat_name})"
                        )
                    )

                    try:
                        request_attempts += 1
                        resp = session.get(page_url, timeout=20)
                        resp.raise_for_status()
                    except Exception as exc:
                        request_failures += 1
                        self.stderr.write(
                            self.style.WARNING(f"  Skipped ({exc})")
                        )
                        continue

                    soup = BeautifulSoup(resp.text, "html.parser")

                    # On these deeper pages the navigation often uses a plain
                    # <ul> without the "caps chevron" classes (e.g.
                    #   <ul>
                    #     <li class="toplevel"><a href="/grocery/241">Baby Products</a></li>
                    #     <li><a href="/grocery/241/502721">Canned Food</a></li>
                    #     ...
                    #   </ul>
                    # )
                    # So instead of relying on specific classes, we look for
                    # anchors whose href starts with the current page path plus
                    # a trailing slash (e.g. "/grocery/241/").
                    parsed = urlparse(page_url)
                    path_prefix = parsed.path.rstrip("/")
                    if not path_prefix:
                        path_prefix = "/"

                    found_any = False
                    for a in soup.find_all("a"):
                        href = (a.get("href") or "").strip()
                        if not href:
                            continue
                        if not href.startswith("/"):
                            continue
                        # We only want links that go deeper under this page,
                        # e.g. "/grocery/241/502721" when the page is
                        # "/grocery/241".
                        if not href.startswith(path_prefix + "/"):
                            continue

                        name = " ".join(a.get_text(" ", strip=True).split())
                        if not name:
                            continue

                        # Build absolute URL for the sub-subcategory
                        full_url = f"{base_url}{href}"

                        # Inspect the live product count instead of assuming
                        # the old 100-product offsets through ?s=700. Bestway
                        # currently paginates in 20-product offsets, and the
                        # total varies by listing.
                        if full_url not in pagination_cache:
                            try:
                                request_attempts += 1
                                listing_response = session.get(
                                    full_url, timeout=20
                                )
                                listing_response.raise_for_status()
                            except Exception as exc:
                                request_failures += 1
                                self.stderr.write(
                                    self.style.WARNING(
                                        "  Could not inspect pagination for "
                                        f"{full_url} ({exc}); recording its "
                                        "first page only."
                                    )
                                )
                                page_urls = [full_url]
                            else:
                                listing_soup = BeautifulSoup(
                                    listing_response.text, "html.parser"
                                )
                                page_urls = (
                                    ProductScraperCommand._listing_page_urls(
                                        full_url, listing_soup
                                    )
                                )
                            pagination_cache[full_url] = page_urls

                        for listing_url in pagination_cache[full_url]:
                            self._add_url(sub_bucket, name, listing_url)
                        found_any = True

                    if not found_any:
                        self.stderr.write(
                            self.style.WARNING(
                                "  No deeper sub-subcategory links found under "
                                f"{parsed.path}"
                            )
                        )

                added = len(sub_bucket) - before
                total_sub_subcats += max(0, added)
                self.stdout.write(
                    f"  Found {added} new sub-subcategories for "
                    f"{main_cat!r} -> {subcat_name!r}"
                )

        self._validate_result(
            categories,
            result,
            output_path,
            request_attempts,
            request_failures,
        )

        # Write the collected data to JSON
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False, indent=2)
        tmp_path.replace(output_path)

        self.stdout.write(
            self.style.SUCCESS(
                f"\nWrote {total_sub_subcats} sub-subcategories across "
                f"{len(result)} main categories to {output_path}"
            )
        )

    @staticmethod
    def _leaf_count(data):
        total = 0
        if not isinstance(data, dict):
            return total
        for subcats in data.values():
            if not isinstance(subcats, dict):
                continue
            for leaves in subcats.values():
                if isinstance(leaves, dict):
                    total += len(leaves)
        return total

    @classmethod
    def _validate_result(
        cls,
        expected,
        result,
        output_path,
        request_attempts,
        request_failures,
    ):
        """Preserve the prior taxonomy when discovery is incomplete."""
        empty_nodes = []
        for main_cat, subcats in expected.items():
            if not isinstance(subcats, dict):
                continue
            result_subcats = result.get(main_cat, {})
            for subcat_name in subcats.keys():
                leaves = result_subcats.get(subcat_name)
                if not isinstance(leaves, dict) or not leaves:
                    empty_nodes.append(f"{main_cat} -> {subcat_name}")

        if empty_nodes:
            preview = ", ".join(empty_nodes[:5])
            suffix = " ..." if len(empty_nodes) > 5 else ""
            raise CommandError(
                "Subcategory discovery was incomplete for "
                f"{preview}{suffix}; existing taxonomy JSON was preserved."
            )

        if request_attempts:
            failure_ratio = request_failures / request_attempts
            if failure_ratio > ProductScraperCommand.MAX_REQUEST_FAILURE_RATIO:
                raise CommandError(
                    "Subcategory request failure rate was "
                    f"{failure_ratio:.1%}; existing taxonomy JSON was preserved."
                )

        if output_path.exists():
            try:
                previous = json.loads(output_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                previous = None
            previous_count = cls._leaf_count(previous)
            current_count = cls._leaf_count(result)
            minimum_count = int(
                previous_count
                * ProductScraperCommand.MIN_OUTPUT_RETENTION_RATIO
            )
            if previous_count and current_count < minimum_count:
                raise CommandError(
                    f"Discovered {current_count:,} taxonomy leaves versus "
                    f"{previous_count:,} previously; existing taxonomy JSON "
                    "was preserved."
                )

    @staticmethod
    def _add_url(bucket, name, url):
        """Merge a URL into the bucket under the given name."""
        existing = bucket.get(name)
        if existing is None:
            bucket[name] = url
            return
        if isinstance(existing, list):
            if url not in existing:
                existing.append(url)
        else:
            if url != existing:
                bucket[name] = [existing, url]

    @staticmethod
    def _normalize_to_list(value):
        """Return a list of URLs from a string or list value."""
        if value is None:
            return []
        if isinstance(value, list):
            return [v for v in value if isinstance(v, str) and v.strip()]
        if isinstance(value, str):
            v = value.strip()
            return [v] if v else []
        return []
