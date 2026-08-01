"""
Scrape product listing pages from Bestway using parent category URLs in
_product_management/management/commands/subcategories.json and export the
results to a JSON file.

Usage:
    python manage.py scraper_for_sub_subcategory

This command:
  - Reads the current parent-category structure from subcategories.json:
        {
          "Main Category": {
            "Subcategory": "https://.../category/401"
          }
        }
  - Reads each live listing's product count and generates its pagination URLs
    using the site's current page size (normally ?s=20, ?s=40, ...)
  - Also accepts the older sub_subcategories.json structure when passed with
    --input
  - Fetches every discovered listing URL
  - Extracts product data from <li data-ga-product-id="..."> elements
  - Follows each product detail page to scrape description / ingredients / other info
  - Writes a flat list of product objects to a JSON file suitable for
    _product_management.management.commands.import_products_from_json
"""

import html
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand, CommandError


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
    MAX_REQUEST_FAILURE_RATIO = 0.20
    MIN_OUTPUT_RETENTION_RATIO = 0.75

    help = (
        "Discover and scrape all paginated Bestway category listings, then "
        "export product data to a JSON file."
    )

    def add_arguments(self, parser):
        script_dir = Path(__file__).resolve().parent

        parser.add_argument(
            "--input",
            type=str,
            default=str(script_dir / "subcategories.json"),
            help=(
                "Path to subcategories.json or the legacy "
                "sub_subcategories.json (default: commands/subcategories.json)."
            ),
        )
        parser.add_argument(
            "--json-out",
            type=str,
            default=str(script_dir / "sub_subcategory_products.json"),
            help=(
                "Path to write scraped products JSON "
                "(default: commands/sub_subcategory_products.json)."
            ),
        )
        parser.add_argument(
            "--base-url",
            type=str,
            default=BASE_URL,
            help="Base site URL (default: https://www.bestwaywholesale.co.uk).",
        )

    def handle(self, *args, **options):
        input_path = Path(options["input"])
        json_out_path = Path(options["json_out"])
        base_url = options["base_url"].rstrip("/")

        if not input_path.exists():
            raise SystemExit(
                f"Input file not found: {input_path}. "
                "Ensure subcategories.json exists (run scrape_subcategories first)."
            )

        with input_path.open(encoding="utf-8") as fh:
            try:
                data = json.load(fh)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"Failed to parse {input_path}: {exc}") from exc

        if not isinstance(data, dict):
            raise SystemExit(
                f"Expected a JSON object in {input_path}, got {type(data).__name__}"
            )

        session = requests.Session()
        session.headers.update(HEADERS)
        self.request_attempts = 0
        self.request_failures = 0

        seeds = list(self._expand_urls(data))
        self.stdout.write(
            f"Found {len(seeds):,} category listing roots in {input_path.name}."
        )
        sources = self._discover_listing_urls(session, seeds, base_url)
        self.stdout.write(
            f"Discovered {len(sources):,} paginated listing URLs to scrape."
        )

        collected: List[Dict] = []
        seen_ids = set()
        list_position = 0

        for main_cat, sub_cat, sub_subcat, url in sources:
            page_url = url.strip()
            if not page_url:
                continue

            if not page_url.startswith("http://") and not page_url.startswith("https://"):
                if not page_url.startswith("/"):
                    page_url = "/" + page_url
                page_url = f"{base_url}{page_url}"

            self.stdout.write(
                self.style.NOTICE(
                    f"→ Fetching: {page_url} "
                    f"({main_cat} -> {sub_cat} -> {sub_subcat})"
                )
            )

            try:
                self.request_attempts += 1
                response = session.get(page_url, timeout=20)
                response.raise_for_status()
            except Exception as exc:
                self.request_failures += 1
                self.stderr.write(self.style.WARNING(f"  skipped ({exc})"))
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            items = soup.select("li[data-ga-product-id]")
            self.stdout.write(f"  found {len(items)} products")

            for li in items:
                ga_id = (li.get("data-ga-product-id") or "").strip()
                if not ga_id:
                    continue
                if ga_id in seen_ids:
                    continue

                seen_ids.add(ga_id)
                list_position += 1

                name = (li.get("data-ga-product-name") or "").strip()
                if not name:
                    name_tag = li.select_one("h2.prodname")
                    if name_tag:
                        name = name_tag.get_text(strip=True)

                price_val = 0.0
                price_raw = (li.get("data-ga-product-price") or "").strip()
                if price_raw:
                    try:
                        price_val = float(price_raw)
                    except ValueError:
                        price_val = 0.0

                cat_raw = (li.get("data-ga-product-category") or "").strip()
                main_category = ""
                sub_category = ""
                sub_subcategory = ""
                if cat_raw:
                    parts = [
                        p.strip()
                        for p in html.unescape(cat_raw).split(">")
                        if p.strip()
                    ]
                    if len(parts) >= 1:
                        main_category = parts[0]
                    if len(parts) >= 2:
                        sub_category = parts[1]
                    if len(parts) >= 3:
                        sub_subcategory = parts[2]

                # Fallback to the path from JSON if the ga-category is missing
                if not main_category:
                    main_category = main_cat or ""
                if not sub_category:
                    sub_category = sub_cat or ""
                if not sub_subcategory:
                    sub_subcategory = sub_subcat or ""

                variant = (li.get("data-ga-product-variant") or "").strip()
                if not variant:
                    size_tag = li.select_one(".prodsize")
                    if size_tag:
                        variant = size_tag.get_text(strip=True)
                # Normalise multiplication symbol
                variant = variant.replace("×", "x")

                relurl = (li.get("data-ga-product-url") or "").strip()
                if not relurl:
                    link = li.select_one("a[data-prodclick], .prodname a")
                    if link and link.has_attr("href"):
                        relurl = (link["href"] or "").strip()

                product_url = ""
                if relurl:
                    product_url = relurl
                    if not product_url.startswith("http://") and not product_url.startswith("https://"):
                        if not product_url.startswith("/"):
                            product_url = "/" + product_url
                        product_url = f"{base_url}{product_url}"

                img_url = None
                img = li.select_one(".prodimageinner img")
                if img and img.has_attr("src"):
                    img_url = (img["src"] or "").strip()
                    if img_url and not img_url.startswith("http://") and not img_url.startswith("https://"):
                        if not img_url.startswith("/"):
                            img_url = "/" + img_url
                        img_url = f"{base_url}{img_url}"

                sku = ""
                sku_tag = li.select_one(".prodsku")
                if sku_tag:
                    sku = (
                        sku_tag.get_text(strip=True)
                        .replace("SKU:", "")
                        .strip()
                    )

                rsp_val = None
                rsp_tag = li.select_one(".prodrsp")
                if rsp_tag:
                    rsp_txt = rsp_tag.get_text(strip=True)
                    rsp_txt = rsp_txt.replace("RSP:", "").replace("RSP", "")
                    rsp_txt = rsp_txt.replace("£", "").replace("\u00a3", "")
                    rsp_txt = rsp_txt.replace(",", "").strip()
                    # Keep only digits and dot
                    cleaned = []
                    for ch in rsp_txt:
                        if ch.isdigit() or ch == ".":
                            cleaned.append(ch)
                    rsp_txt = "".join(cleaned)
                    if rsp_txt:
                        try:
                            rsp_val = float(rsp_txt)
                        except ValueError:
                            rsp_val = None

                # Try to infer retail_EAN from image filename or, as a fallback,
                # from the product URL path. We only accept plausible GTIN/EAN
                # lengths (8, 12, 13, 14 digits).
                retail_ean = ""

                def _extract_ean_from_url(u: str) -> str:
                    if not u:
                        return ""
                    parsed = urlparse(u)
                    path = parsed.path or u
                    # Take last path segment, strip query/fragment/extension
                    last = path.rsplit("/", 1)[-1]
                    last = last.split("?", 1)[0].split("#", 1)[0]
                    stem = last.split(".", 1)[0]
                    digits = re.sub(r"\D+", "", stem or "")
                    if len(digits) in (8, 12, 13, 14):
                        return digits
                    return ""

                for candidate in (img_url, product_url):
                    cand_ean = _extract_ean_from_url(candidate or "")
                    if cand_ean:
                        retail_ean = cand_ean
                        break

                # Promotion / multibuy parsing from the listing item text
                item_text = li.get_text(" ", strip=True)
                promotion_end_date = None
                multi_buy = False

                if item_text:
                    # e.g. "Promotion ends 30th Jan"
                    m = re.search(
                        r"Promotion ends\s*(\d+\w*\s+\w+)",
                        item_text,
                        flags=re.IGNORECASE,
                    )
                    if m:
                        promotion_end_date = m.group(1).strip()

                    if "multibuy" in item_text.lower():
                        multi_buy = True

                desc_text, ingr_text, other_info_text, vat_rate_code = (
                    self._scrape_product_details(product_url)
                )

                row = {
                    "ga_product_id": ga_id,
                    "name": name,
                    "price": price_val,
                    "main_category": main_category,
                    "sub_category": sub_category,
                    "sub_subcategory": sub_subcategory,
                    "variant": variant,
                    "list_position": list_position,
                    "url": product_url,
                    "image_url": img_url,
                    "sku": sku,
                    "rsp": rsp_val,
                    "promotion_end_date": promotion_end_date,
                    "multi_buy": multi_buy,
                    "retail_EAN": retail_ean,
                    "description": desc_text,
                    "ingredients_nutrition": ingr_text,
                    "other_info": other_info_text,
                    # Do not hard-default here; keep whatever we could
                    # infer from the product page (or None). The
                    # import_products_from_json command will fall back
                    # to "standard" if this is falsy.
                    "vat_rate": vat_rate_code,
                }

                collected.append(row)

        self._validate_scrape_result(data, collected, json_out_path)

        json_out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = json_out_path.with_suffix(json_out_path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as jf:
            json.dump(collected, jf, ensure_ascii=False, indent=2)
        tmp_path.replace(json_out_path)

        self.stdout.write(
            self.style.SUCCESS(
                f"\nScraped {len(collected):,} unique products and wrote them to {json_out_path}"
            )
        )

    @staticmethod
    def _expand_urls(data: Dict) -> Iterable[Tuple[str, str, str, str]]:
        """
        Flatten either supported input structure into
        (main_category, sub_category, sub_subcategory, url) tuples.

        The current subcategories.json format stores a URL directly under each
        subcategory. The legacy sub_subcategories.json format has one further
        mapping level and may contain a list of pre-generated pagination URLs.
        """
        for main_cat, subcats in data.items():
            if not isinstance(subcats, dict):
                continue
            for sub_cat, value in subcats.items():
                if isinstance(value, dict):
                    for sub_subcat, nested_value in value.items():
                        yield from Command._yield_url_values(
                            main_cat, sub_cat, sub_subcat, nested_value
                        )
                else:
                    yield from Command._yield_url_values(
                        main_cat, sub_cat, "", value
                    )

    @staticmethod
    def _yield_url_values(main_cat, sub_cat, sub_subcat, value):
        if isinstance(value, list):
            for url in value:
                if isinstance(url, str) and url.strip():
                    yield main_cat, sub_cat, sub_subcat, url
        elif isinstance(value, str) and value.strip():
            yield main_cat, sub_cat, sub_subcat, value

    @staticmethod
    def _category_key(value):
        text = (value or "").replace("&", " and ").casefold()
        return " ".join(re.findall(r"[a-z0-9]+", text))

    def _validate_scrape_result(self, input_data, collected, output_path):
        """Refuse to replace the last product file with partial scrape data."""
        if not collected:
            raise CommandError(
                "Scrape produced no products; existing product JSON was preserved."
            )

        expected_categories = {
            self._category_key(name): name
            for name, value in input_data.items()
            if isinstance(value, dict) and self._category_key(name)
        }
        collected_category_keys = {
            self._category_key(row.get("main_category"))
            for row in collected
            if isinstance(row, dict)
        }
        missing = [
            label
            for key, label in expected_categories.items()
            if key not in collected_category_keys
        ]
        if missing:
            raise CommandError(
                "Scrape is incomplete; missing main categories: "
                f"{', '.join(sorted(missing, key=str.casefold))}. "
                "Existing product JSON was preserved."
            )

        if self.request_attempts:
            failure_ratio = self.request_failures / self.request_attempts
            if failure_ratio > self.MAX_REQUEST_FAILURE_RATIO:
                raise CommandError(
                    "Scrape request failure rate was "
                    f"{failure_ratio:.1%}, above the allowed "
                    f"{self.MAX_REQUEST_FAILURE_RATIO:.0%}; existing product "
                    "JSON was preserved."
                )

        if output_path.exists():
            try:
                previous = json.loads(output_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                previous = None
            if isinstance(previous, list) and previous:
                minimum_count = int(
                    len(previous) * self.MIN_OUTPUT_RETENTION_RATIO
                )
                if len(collected) < minimum_count:
                    raise CommandError(
                        f"Scrape produced {len(collected):,} products versus "
                        f"{len(previous):,} previously; existing product JSON "
                        "was preserved."
                    )

    def _discover_listing_urls(self, session, seeds, base_url):
        """
        Replace stale, pre-generated pagination with URLs calculated from each
        live category page's "1 to N of Total Products" summary.
        """
        discovered = []
        seen_roots = set()

        for main_cat, sub_cat, sub_subcat, raw_url in seeds:
            root_url = self._listing_root_url(raw_url, base_url)
            if not root_url or root_url in seen_roots:
                continue
            seen_roots.add(root_url)

            self.stdout.write(
                self.style.NOTICE(
                    f"Inspecting pagination: {root_url} "
                    f"({main_cat} -> {sub_cat})"
                )
            )

            try:
                self.request_attempts += 1
                response = session.get(root_url, timeout=20)
                response.raise_for_status()
            except Exception as exc:
                self.request_failures += 1
                self.stderr.write(
                    self.style.WARNING(
                        f"  Could not inspect pagination ({exc}); "
                        "the first page will still be attempted."
                    )
                )
                page_urls = [root_url]
            else:
                soup = BeautifulSoup(response.text, "html.parser")
                page_urls = self._listing_page_urls(root_url, soup)

            self.stdout.write(f"  discovered {len(page_urls)} page(s)")
            discovered.extend(
                (main_cat, sub_cat, sub_subcat, page_url)
                for page_url in page_urls
            )

        return discovered

    @staticmethod
    def _listing_root_url(raw_url, base_url):
        """Return an absolute listing URL with any stale ``s`` offset removed."""
        url = (raw_url or "").strip()
        if not url:
            return ""
        if not url.startswith(("http://", "https://")):
            if not url.startswith("/"):
                url = "/" + url
            url = f"{base_url}{url}"

        parsed = urlsplit(url)
        query = [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key.lower() != "s"
        ]
        return urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, urlencode(query), "")
        )

    @staticmethod
    def _listing_page_urls(root_url, soup):
        """
        Calculate every page URL from Bestway's live result summary.

        For example, "1 to 20 of 112 Products" produces the root page followed
        by ?s=20, ?s=40, ?s=60, ?s=80 and ?s=100.
        """
        summary = re.search(
            r"(\d[\d,]*)\s+to\s+(\d[\d,]*)\s+of\s+"
            r"(\d[\d,]*)\s+Products",
            soup.get_text(" ", strip=True),
            flags=re.IGNORECASE,
        )
        if not summary:
            return [root_url]

        first = int(summary.group(1).replace(",", ""))
        last = int(summary.group(2).replace(",", ""))
        total = int(summary.group(3).replace(",", ""))
        page_size = last - first + 1
        if page_size <= 0 or total <= page_size:
            return [root_url]

        parsed = urlsplit(root_url)
        base_query = [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key.lower() != "s"
        ]
        urls = [root_url]
        for offset in range(page_size, total, page_size):
            query = urlencode([*base_query, ("s", str(offset))])
            urls.append(
                urlunsplit(
                    (parsed.scheme, parsed.netloc, parsed.path, query, "")
                )
            )
        return urls

    @staticmethod
    def _clean_text(el) -> str:
        if not el:
            return ""
        text = el.get_text("\n", strip=True)
        lines = [ln.strip() for ln in text.splitlines()]
        lines = [ln for ln in lines if ln]
        return "\n".join(lines).strip()

    def _scrape_product_details(self, url):
        """
        Fetch product detail page and extract:
        - Description
        - Ingredients/Nutrition (combined bucket)
        - Other Info (remaining sections)
        - VAT rate (mapped to model-style codes)

        Returns a 4-tuple (each may be None):
        (description, ingredients_nutrition, other_info, vat_rate_code)
        """
        if not url:
            return None, None, None, None
        try:
            self.request_attempts += 1
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
        except Exception:
            self.request_failures += 1
            return None, None, None, None

        soup = BeautifulSoup(r.text, "html.parser")

        description: List[str] = []
        ingredients_nutrition: List[str] = []
        other_info: List[str] = []

        for btn in soup.select(".accordionButton"):
            title = (btn.get_text(strip=True) or "").lower()
            content = btn.find_next_sibling(
                lambda tag: tag.name == "div"
                and "accordionContent" in tag.get("class", [])
                and "prodtabcontents" in tag.get("class", [])
            )
            text = self._clean_text(content)
            if not text:
                continue

            if any(
                k in title
                for k in ["description", "product details", "about", "overview"]
            ):
                description.append(text)
            elif any(
                k in title
                for k in [
                    "ingredient",
                    "nutrition",
                    "nutritional",
                    "allergen",
                    "allergy",
                    "dietary",
                    "diet",
                ]
            ):
                ingredients_nutrition.append(
                    f"{btn.get_text(strip=True)}\n{text}"
                )
            else:
                other_info.append(f"{btn.get_text(strip=True)}\n{text}")

        # VAT rate from the specification table, mirroring
        # update_vat_rates.extract_vat_rate/map_vat_rate logic.
        vat_rate_raw = None
        table = soup.find("table", class_="prodtable")
        if table:
            for row in table.find_all("tr"):
                header = row.find("th")
                if header and "Vat Rate" in header.get_text():
                    vat_rate_td = row.find("td")
                    if vat_rate_td:
                        vat_rate_raw = vat_rate_td.get_text(strip=True).lower()
                    break

        vat_rate_code = self._map_vat_rate(vat_rate_raw) if vat_rate_raw else None

        def join_or_none(parts: List[str]):
            s = "\n\n".join(p for p in parts if p)
            return s if s else None

        return (
            join_or_none(description),
            join_or_none(ingredients_nutrition),
            join_or_none(other_info),
            vat_rate_code,
        )

    @staticmethod
    def _map_vat_rate(vat_rate_str):
        """
        Map scraped VAT rate text to the model's VAT_RATE_CHOICES.
        Mirrors the logic in update_vat_rates.map_vat_rate.
        """
        if not vat_rate_str:
            return None

        mapping = {
            "standard": "standard",
            "reduced": "reduced",
            "zero": "zero",
            "exempt": "exempt",
            "exempted": "exempt",
            "zero-rated": "zero",
            "5%": "5%",
        }

        vat_rate_normalized = (
            vat_rate_str.replace("%", "").replace("rate", "").strip().lower()
        )

        if vat_rate_normalized in mapping:
            return mapping[vat_rate_normalized]

        if "exempt" in vat_rate_normalized:
            return "exempt"
        if "zero" in vat_rate_normalized:
            return "zero"
        if "reduced" in vat_rate_normalized:
            return "reduced"
        if "standard" in vat_rate_normalized:
            return "standard"

        return None
