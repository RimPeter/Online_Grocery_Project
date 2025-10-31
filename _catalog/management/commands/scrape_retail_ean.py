# python manage.py scrape_retail_ean --only-domain bestwaywholesale.co.uk

from django.core.management.base import BaseCommand
from django.db.models import Q
from _catalog.models import All_Products

import json
import re
import time
from typing import Any, Iterable, Optional

import requests
from bs4 import BeautifulSoup


GTIN_KEYS = {
    "gtin", "gtin8", "gtin12", "gtin13", "gtin14",
    "ean", "ean8", "ean13", "barcode"
}


def _digits(s: str) -> str:
    return re.sub(r"\D+", "", s or "")


def _ean13_checksum_valid(code: str) -> bool:
    if not code or len(code) != 13 or not code.isdigit():
        return False
    digits = [int(c) for c in code]
    s = sum(digits[i] * (3 if i % 2 else 1) for i in range(12))
    check = (10 - (s % 10)) % 10
    return check == digits[12]


def _normalize_gtin(val: str) -> Optional[str]:
    """Return a normalized EAN value to store in retail_EAN.

    Preference order:
    - Valid EAN-13
    - If 14 digits and dropping leading zero yields valid EAN-13
    - EAN-8 (leave as-is)
    Otherwise None.
    """
    d = _digits(val)
    if len(d) == 13 and _ean13_checksum_valid(d):
        return d
    if len(d) == 14 and d.startswith("0"):
        d13 = d[1:]
        if _ean13_checksum_valid(d13):
            return d13
    if len(d) == 8 and d.isdigit():
        return d
    return None


def _iter_json_values(obj: Any) -> Iterable[Any]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _iter_json_values(v)
    elif isinstance(obj, list):
        for it in obj:
            yield from _iter_json_values(it)
    else:
        yield obj


def _extract_from_jsonld(soup: BeautifulSoup) -> Optional[str]:
    for tag in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
        try:
            data = json.loads(tag.string or "")
        except Exception:
            continue
        # Look for keys like gtin13/ean13 and their values
        stack = [data]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                for k, v in cur.items():
                    lk = str(k).strip().lower()
                    if lk in GTIN_KEYS and isinstance(v, (str, int)):
                        val = str(v)
                        norm = _normalize_gtin(val)
                        if norm:
                            return norm
                    if isinstance(v, (dict, list)):
                        stack.append(v)
            elif isinstance(cur, list):
                stack.extend(cur)
    return None


def _extract_from_dom(soup: BeautifulSoup) -> Optional[str]:
    # Common label + value patterns (tables, definition lists, etc.)
    label_regex = re.compile(r"\b(EAN|GTIN|Barcode|Bar\s*code)\b", re.I)

    # Look for label cells
    for th in soup.find_all(["th", "td", "dt", "label"]):
        if not th.get_text(strip=True):
            continue
        if label_regex.search(th.get_text(" ", strip=True)):
            # Prefer next sibling text
            sib = th.find_next_sibling(["td", "dd", "span", "div"]) or th.parent.find_next_sibling()
            if sib:
                cand = sib.get_text(" ", strip=True)
                norm = _normalize_gtin(cand)
                if norm:
                    return norm

    # Fallback: search full text
    text = soup.get_text(" ", strip=True)
    for m in re.finditer(r"\b(?:EAN|GTIN|Barcode)\s*[:#-]?\s*([0-9\s-]{8,18})\b", text, re.I):
        norm = _normalize_gtin(m.group(1))
        if norm:
            return norm

    return None


def _find_ean_in_html(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, "html.parser")
    return _extract_from_jsonld(soup) or _extract_from_dom(soup)


class Command(BaseCommand):
    help = "Scrape product detail pages to populate retail_EAN for products where it is missing."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0, help="Max number of products to process")
        parser.add_argument("--force", action="store_true", help="Re-scrape and overwrite existing retail_EAN values")
        parser.add_argument("--dry-run", action="store_true", help="Parse and report found EANs without saving")
        parser.add_argument("--sleep", type=float, default=0.5, help="Seconds to sleep between requests")
        parser.add_argument("--only-domain", type=str, default="", help="Only process products whose URL contains this domain substring")

    def handle(self, *args, **opts):
        limit = int(opts.get("limit") or 0)
        force = bool(opts.get("force"))
        dry_run = bool(opts.get("dry_run"))
        delay = float(opts.get("sleep") or 0)
        only_domain = (opts.get("only_domain") or "").strip()

        qs = All_Products.objects.all()
        if not force:
            qs = qs.filter(Q(retail_EAN__isnull=True) | Q(retail_EAN=""))
        if only_domain:
            qs = qs.filter(url__icontains=only_domain)
        qs = qs.exclude(url__isnull=True).exclude(url="").order_by("id")
        if limit:
            qs = qs[:limit]

        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; EANScraper/1.0; +https://example.local)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.9",
            "Connection": "close",
        })

        processed = 0
        updated = 0
        skipped = 0
        errors = 0

        for p in qs:
            processed += 1
            url = (p.url or "").strip()
            if not url:
                skipped += 1
                continue
            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
                ean = _find_ean_in_html(resp.text)
                if ean:
                    if dry_run:
                        self.stdout.write(f"{p.id} {p.name[:60]!r} -> EAN {ean} (dry-run)")
                    else:
                        p.retail_EAN = ean
                        p.save(update_fields=["retail_EAN"])
                        updated += 1
                        self.stdout.write(self.style.SUCCESS(f"Updated {p.id} with EAN {ean}"))
                else:
                    self.stdout.write(self.style.WARNING(f"No EAN found for {p.id} {url}"))
            except Exception as exc:
                errors += 1
                self.stderr.write(f"Error processing {p.id} {url}: {exc}")
            finally:
                if delay:
                    time.sleep(delay)

        self.stdout.write("")
        self.stdout.write(f"Processed: {processed}")
        if not dry_run:
            self.stdout.write(f"Updated:   {updated}")
        self.stdout.write(f"Skipped:   {skipped}")
        self.stdout.write(f"Errors:    {errors}")

