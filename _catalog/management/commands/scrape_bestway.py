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
        with open(json_path, encoding="utf-8") as fh:
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

                    # avoid double work if the same product ID appears in
                    # multiple category pages
                    if ga_id in seen_ids:
                        continue

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

                    # scrape product detail page for extended fields
                    product_url = defaults.get("url")
                    desc_text, ingr_text, other_info_text = self._scrape_product_details(product_url)

                    # upsert base fields
                    obj, _ = All_Products.objects.update_or_create(
                        ga_product_id=ga_id, defaults=defaults
                    )

                    # set extended fields if present on the model
                    updated_fields = []
                    if hasattr(obj, "description") and desc_text is not None:
                        setattr(obj, "description", desc_text)
                        updated_fields.append("description")
                    if hasattr(obj, "ingredients_nutrition") and ingr_text is not None:
                        setattr(obj, "ingredients_nutrition", ingr_text)
                        updated_fields.append("ingredients_nutrition")
                    if hasattr(obj, "other_info") and other_info_text is not None:
                        setattr(obj, "other_info", other_info_text)
                        updated_fields.append("other_info")
                    if updated_fields:
                        try:
                            obj.save(update_fields=updated_fields)
                        except Exception:
                            # fall back to full save if update_fields fails for any reason
                            obj.save()

                    seen_ids.add(ga_id)
                    upserted += 1

        self.stdout.write(self.style.SUCCESS(f"\nUpserted {upserted:,} products."))

    @staticmethod
    def _clean_text(el) -> str:
        if not el:
            return ""
        # Get text with line breaks for block elements
        text = el.get_text("\n", strip=True)
        # Normalize excessive whitespace/newlines
        lines = [ln.strip() for ln in text.splitlines()]
        lines = [ln for ln in lines if ln]
        return "\n".join(lines).strip()

    def _scrape_product_details(self, url):
        """
        Fetch product detail page and extract three fields:
        - Description
        - Ingredients/Nutrition (combined bucket)
        - Other Info (remaining sections)

        Returns a 3-tuple of strings (or None if not found):
        (description, ingredients_nutrition, other_info)
        """
        if not url:
            return None, None, None
        try:
            r = requests.get(url, timeout=20)
            r.raise_for_status()
        except Exception:
            return None, None, None

        soup = BeautifulSoup(r.text, "html.parser")

        # The product detail tabs are structured as pairs of
        #   <div class="accordionButton">Title</div>
        #   <div class="accordionContent prodtabcontents">...</div>
        # Titles vary per page, so we categorize by keywords.
        description = []
        ingredients_nutrition = []
        other_info = []

        for btn in soup.select(".accordionButton"):
            title = (btn.get_text(strip=True) or "").lower()
            content = btn.find_next_sibling(lambda tag: tag.name == "div" and "accordionContent" in tag.get("class", []) and "prodtabcontents" in tag.get("class", []))
            text = self._clean_text(content)
            if not text:
                continue

            if any(k in title for k in ["description", "product details", "about", "overview"]):
                description.append(text)
            elif any(k in title for k in [
                "ingredient", "nutrition", "nutritional", "allergen", "allergy", "dietary", "diet"]):
                ingredients_nutrition.append(f"{btn.get_text(strip=True)}\n{text}")
            else:
                # Keep header to preserve context in other_info
                other_info.append(f"{btn.get_text(strip=True)}\n{text}")

        def join_or_none(parts):
            s = "\n\n".join(p for p in parts if p)
            return s if s else None

        return (
            join_or_none(description),
            join_or_none(ingredients_nutrition),
            join_or_none(other_info),
        )
