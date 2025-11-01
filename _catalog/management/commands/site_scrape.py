"""
Django management command: site_scrape

Scrapes category and subcategory URLs from Bestway Wholesale starter pages
and updates the JSON mapping at `_catalog/management/commands/product_category.json`.

Usage:
  python manage.py site_scrape                # scrape with default starter pages
  python manage.py site_scrape --dry-run      # just print summary, do not write
  python manage.py site_scrape --urls-file F  # provide custom starter URLs (one per line or JSON list)

Notes:
- Follows the approach outlined in `site_scrape_plan.txt`:
  1) Start from top-level pages (e.g., bread-cakes, chilled-fresh, ...)
  2) Extract subcategory links from `<ul class="caps chevron">`
  3) For each sub-subcategory page, detect an extra page `?s=100` and store as a list
- Updates `product_category.json` without breaking structure by merging keys
  for the scraped category group; existing unrelated keys are preserved.
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


BESTWAY_BASE = "https://www.bestwaywholesale.co.uk"


def _abs_url(href: str) -> str:
    href = (href or "").strip()
    if not href:
        return href
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("/"):
        return f"{BESTWAY_BASE}{href}"
    return f"{BESTWAY_BASE}/{href}"


def _fetch(url: str, timeout: int = 20) -> Optional[BeautifulSoup]:
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception:
        return None


def _extract_caps_chevron_links(soup: BeautifulSoup) -> List[Tuple[str, str]]:
    """Return list of (name, absolute_url) from ul.caps.chevron anchors."""
    out: List[Tuple[str, str]] = []
    for a in soup.select("ul.caps.chevron li a"):
        name = a.get_text(strip=True)
        href = _abs_url(a.get("href", ""))
        if name and href:
            out.append((name, href))
    return out


def _has_second_page(soup: BeautifulSoup, url: str) -> bool:
    """
    Heuristic: if any anchor on the page links to the same path with '?s=100'
    it indicates an additional page. We check against the URL's path.
    """
    try:
        # Normalize without query
        path = re.sub(r"\?.*$", "", url)
        path_100 = f"{path}?s=100"
        selector_hits = soup.select(f"a[href='{path_100}']")
        if selector_hits:
            return True
        # Fallback: any anchor containing '?s=100' on same base path
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            if href.endswith("?s=100") and href.startswith(path):
                return True
    except Exception:
        pass
    return False


def _scrape_leaf_categories(subcat_url: str) -> Dict[str, List[str] or str]:
    """
    Given a subcategory page (e.g., /bread-cakes/401), try to find leaf
    categories beneath it. If leaf categories are present as another
    ul.caps.chevron, collect those. If not, treat the subcategory itself as
    a leaf list.

    For each leaf, detect if there is a second page '?s=100' and store
    either a single URL string or [url, url?s=100].
    """
    results: Dict[str, List[str] or str] = {}
    soup = _fetch(subcat_url)
    if not soup:
        return results

    links = _extract_caps_chevron_links(soup)

    # If we found deeper leaves in the caps chevron list, use those as leaves
    candidate_leaf_links: List[Tuple[str, str]]
    if links:
        # Heuristic: consider only links that extend the subcat path with an
        # extra segment (e.g., /bread-cakes/401/503311)
        sub_path = re.sub(r"\?.*$", "", subcat_url)
        candidate_leaf_links = [
            (n, u) for (n, u) in links if re.sub(r"\?.*$", "", u).startswith(sub_path + "/")
        ]
        # If heuristic yields nothing, fall back to all links we saw
        if not candidate_leaf_links:
            candidate_leaf_links = links
    else:
        candidate_leaf_links = []

    if not candidate_leaf_links:
        # Treat the subcategory page itself as a leaf page of products
        leaf_name = subcat_url.rstrip("/").split("/")[-1]
        # Name from breadcrumb if possible
        crumb = soup.select_one(".breadcrumb li:last-child, .breadcrumb li a[href]")
        if crumb:
            txt = crumb.get_text(strip=True)
            if txt:
                leaf_name = txt
        second_page = _has_second_page(soup, subcat_url)
        if second_page:
            results[leaf_name] = [subcat_url, re.sub(r"\?.*$", "", subcat_url) + "?s=100"]
        else:
            results[leaf_name] = subcat_url
        return results

    # Otherwise, iterate each leaf link and optionally include '?s=100'
    for leaf_name, leaf_url in candidate_leaf_links:
        leaf_soup = _fetch(leaf_url)
        if not leaf_soup:
            results[leaf_name] = leaf_url
            continue
        if _has_second_page(leaf_soup, leaf_url):
            results[leaf_name] = [leaf_url, re.sub(r"\?.*$", "", leaf_url) + "?s=100"]
        else:
            results[leaf_name] = leaf_url
    return results


def _default_starter_urls() -> List[str]:
    # From site_scrape_plan.txt starter sites
    return [
        f"{BESTWAY_BASE}/bread-cakes",
        f"{BESTWAY_BASE}/chilled-fresh",
        f"{BESTWAY_BASE}/frozen",
        f"{BESTWAY_BASE}/grocery",
        f"{BESTWAY_BASE}/soft-drinks",
        f"{BESTWAY_BASE}/beers-wines-spirits",
        f"{BESTWAY_BASE}/cigarettes-tobacco",
        f"{BESTWAY_BASE}/non-food",
        f"{BESTWAY_BASE}/confectionery",
    ]


def _category_group_name(soup: BeautifulSoup, fallback_from_url: str) -> str:
    # Prefer breadcrumb text
    crumb = soup.select_one(".breadcrumb li a[href]")
    if crumb:
        name = crumb.get_text(strip=True)
        if name:
            return name
    # Fallback to last path segment prettified
    segment = fallback_from_url.rstrip("/").split("/")[-1]
    name = segment.replace("-", " ").title()
    return name


def _load_json(path: Path) -> Dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _dump_json(path: Path, data: Dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


class Command(BaseCommand):
    help = "Scrape Bestway category/subcategory URLs and update product_category.json"

    def add_arguments(self, parser):
        parser.add_argument(
            "--urls-file",
            dest="urls_file",
            default=None,
            help="Path to a text/JSON file listing starter URLs",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not write changes; print summary only",
        )

    def _load_starter_urls(self, urls_file: Optional[str]) -> List[str]:
        if not urls_file:
            return _default_starter_urls()
        p = Path(urls_file)
        if not p.exists():
            raise CommandError(f"Starter URLs file not found: {urls_file}")
        text = p.read_text(encoding="utf-8").strip()
        if not text:
            return []
        # Accept JSON list or newline separated text
        try:
            j = json.loads(text)
            if isinstance(j, list):
                return [str(x) for x in j]
        except Exception:
            pass
        # Fallback to lines
        return [line.strip() for line in text.splitlines() if line.strip()]

    def handle(self, *args, **options):
        urls_file = options.get("urls_file")
        dry_run = options.get("dry_run")

        starter_urls = self._load_starter_urls(urls_file)
        if not starter_urls:
            raise CommandError("No starter URLs provided or found.")

        json_path = (
            Path(settings.BASE_DIR)
            / "_catalog"
            / "management"
            / "commands"
            / "product_category.json"
        )
        data = _load_json(json_path)

        updated_groups = 0
        total_leaves = 0

        for start_url in starter_urls:
            self.stdout.write(self.style.NOTICE(f"Scanning: {start_url}"))
            soup = _fetch(start_url)
            if not soup:
                self.stderr.write(self.style.WARNING("  failed to fetch, skipping"))
                continue

            group_name = _category_group_name(soup, start_url)
            sub_links = _extract_caps_chevron_links(soup)
            if not sub_links:
                self.stderr.write(self.style.WARNING("  no subcategory links found; skipping"))
                continue

            group_map: Dict[str, List[str] or str] = {}
            for sub_name, sub_url in sub_links:
                leaf_map = _scrape_leaf_categories(sub_url)
                # Merge leaf_map into group_map (later duplicates override)
                for leaf_name, value in leaf_map.items():
                    group_map[leaf_name] = value

            if not group_map:
                self.stderr.write(self.style.WARNING("  no leaves discovered; skipping"))
                continue

            total_leaves += len(group_map)
            data[group_name] = group_map
            updated_groups += 1
            self.stdout.write(self.style.SUCCESS(f"  -> {group_name}: {len(group_map)} leaves"))

        if dry_run:
            self.stdout.write("\nDry-run summary:")
            self.stdout.write(f"  Updated groups: {updated_groups}")
            self.stdout.write(f"  Total leaves:   {total_leaves}")
            return

        # Write backup then save
        backup_path = json_path.with_suffix(".backup.json")
        if not backup_path.exists():
            try:
                backup_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                self.stdout.write(self.style.NOTICE(f"Backup written: {backup_path}"))
            except Exception:
                # Non-fatal if backup fails
                pass

        _dump_json(json_path, data)
        self.stdout.write(self.style.SUCCESS(
            f"\nUpdated product_category.json — {updated_groups} groups, {total_leaves} leaves"
        ))

