# _catalog/management/commands/scrape_bestway.py
# Run with: python manage.py scrape_bestway

import json
import os
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.db import transaction

from django.conf import settings
from _catalog.models import All_Products


class Command(BaseCommand):
    help = "Scrape all Bestway category pages (taken from product_category.json) and upsert them into All_Products."

    #──── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def load_category_json():
        json_path = (
            Path(settings.BASE_DIR)
            / "_catalog"
            / "management"
            / "commands"
            / "product_category.json"
        )
        with open(json_path, encoding="utf‑8") as fh:
            return json.load(fh)

    @staticmethod
    def expand_urls(category_data):
        """
        Yields tuples: (level1, level2 or None, url_string)
        """
        for level1, node in category_data.items():
            # branch → dict of level‑2 names
            if isinstance(node, dict):
                for level2, url_or_list in node.items():
                    if isinstance(url_or_list, list):
                        for u in url_or_list:
                            yield level1, level2, u
                    else:
                        yield level1, level2, url_or_list
            # leaf → string or list
            else:
                if isinstance(node, list):
                    for u in node:
                        yield level1, None, u
                else:
                    yield level1, None, node

    #──── main handler ─────────────────────────────────────────────────────

    def handle(self, *args, **options):
        category_data = self.load_category_json()
        sources = list(self.expand_urls(category_data))
        self.stdout.write(f"Found {len(sources):,} category URLs to scrape.")

        upserted = 0
        seen_ids = set()
        list_position = 0

        # wrap the whole run in a single transaction for speed
        with transaction.atomic():
            for level1, level2, url in sources:
                self.stdout.write(self.style.NOTICE(f"› {url}"))
                try:
                    response = requests.get(url, timeout=20)
                    response.raise_for_status()
                except Exception as exc:
                    self.stderr.write(self.style.WARNING(f"  skipped ({exc})"))
                    continue

                soup = BeautifulSoup(response.text, "html.parser")

                for li in soup.select("li[data-ga-product-id]"):
                    list_position += 1

                    ga_id  = li.get("data-ga-product-id", "").strip()
                    name   = li.get("data-ga-product-name", "").strip()
                    price  = float(li.get("data-ga-product-price", 0) or 0)
                    cat    = li.get("data-ga-product-category", "").strip()
                    var    = li.get("data-ga-product-variant", "").strip()
                    relurl = li.get("data-ga-product-url", "").strip()

                    img = li.select_one(".prodimageinner img")
                    img_url = img["src"].strip() if img and img.has_attr("src") else None

                    sku_tag = li.select_one(".prodsku")
                    sku = (sku_tag.get_text(strip=True)
                                    .replace("SKU:", "")
                                    .strip()) if sku_tag else ""

                    rsp_tag = li.select_one(".prodrsp")
                    rsp_val = 0
                    if rsp_tag:
                        rsp_txt = rsp_tag.get_text(strip=True) \
                                         .replace("RSP:", "") \
                                         .replace("£", "") \
                                         .strip()
                        try:
                            rsp_val = float(rsp_txt)
                        except ValueError:
                            pass

                    # build dict for update_or_create
                    defaults = dict(
                        name=name,
                        price=price,
                        main_category=cat,
                        variant=var,
                        list_position=list_position,
                        url=f"https://www.bestwaywholesale.co.uk{relurl}",
                        image_url=img_url,
                        sku=sku,
                        rsp=rsp_val,
                        promotion_end_date=None,
                        multi_buy=False,
                        retail_EAN="",
                        vat_rate="standard",
                        sub_category=level1,
                        sub_subcategory=level2 or "",
                    )

                    # avoid double work if the same product ID appears in
                    # multiple category pages
                    if ga_id in seen_ids:
                        continue
                    seen_ids.add(ga_id)

                    All_Products.objects.update_or_create(
                        ga_product_id=ga_id, defaults=defaults
                    )
                    upserted += 1

        self.stdout.write(self.style.SUCCESS(f"\nUpserted {upserted:,} products."))
