# python manage.py scrape_bestway_breadcakes


import requests
from bs4 import BeautifulSoup
import json
import os

from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Scrapes product data from multiple Bestway Wholesale pages and saves it to JSON."

    def handle(self, *args, **options):
        # The three URLs you want to scrape
        
        urls_file = os.path.join(os.path.dirname(__file__), 'urls.json')
        with open(urls_file, 'r', encoding='utf-8') as f:
            urls = json.load(f)
        
        all_products = []
        list_position = 0

        for url in urls:
            # Make a request to the page
            response = requests.get(url)
            response.raise_for_status()  # Raise an exception on 4xx/5xx errors

            soup = BeautifulSoup(response.text, "html.parser")

            # Each product is in <li data-ga-product-id="...">
            product_list_items = soup.select('li[data-ga-product-id]')

            for li in product_list_items:
                list_position += 1

                ga_product_id = li.get("data-ga-product-id", "").strip()
                ga_product_name = li.get("data-ga-product-name", "").strip()
                ga_product_price = li.get("data-ga-product-price", "0").strip()
                ga_product_category = li.get("data-ga-product-category", "").strip()
                ga_product_variant = li.get("data-ga-product-variant", "").strip()
                ga_product_url = li.get("data-ga-product-url", "").strip()

                # Split category into main, sub and sub-sub
                categories = [c.strip() for c in ga_product_category.split('>')]
                main_category = categories[0] if len(categories) > 0 else ''
                sub_category = categories[1] if len(categories) > 1 else ''
                sub_subcategory = categories[2] if len(categories) > 2 else ''

                # Extract image URL
                img_tag = li.select_one(".prodimageinner img")
                image_url = img_tag["src"].strip() if img_tag and img_tag.has_attr("src") else None

                # Extract SKU
                sku_tag = li.select_one(".prodsku")
                sku_text = sku_tag.get_text(strip=True) if sku_tag else ""
                # Example format is "SKU: 807771"
                sku = sku_text.replace("SKU:", "").strip() if "SKU:" in sku_text else ""

                # Extract RSP (like "RSP: £1.99")
                rsp_tag = li.select_one(".prodrsp")
                rsp_text = rsp_tag.get_text(strip=True) if rsp_tag else ""
                # Remove "RSP:" / "£" from the string to get just the numeric part
                rsp_numeric_str = rsp_text.replace("RSP:", "").replace("£", "").strip()
                try:
                    rsp_value = float(rsp_numeric_str)
                except ValueError:
                    rsp_value = 0.0

                product_data = {
                    "ga_product_id": ga_product_id,
                    "name": ga_product_name,
                    "price": float(ga_product_price) if ga_product_price else 0.0,
                    "main_category": main_category,
                    "sub_category": sub_category,
                    "sub_subcategory": sub_subcategory,
                    "variant": ga_product_variant,
                    "list_position": list_position,
                    "url": f"https://www.bestwaywholesale.co.uk{ga_product_url}",
                    "image_url": image_url,
                    "sku": sku,
                    "rsp": rsp_value,  # numeric value
                    "promotion_end_date": None,  # Not scraped
                    "multi_buy": False,          # Not scraped
                    "retail_EAN": "",            # Not scraped
                    "vat_rate": "standard",      # Default assumption
                }

                all_products.append(product_data)

        # Remove duplicates by ga_product_id if it appears in multiple URLs
        # (We keep the first occurrence; or you can override with the last if you prefer.)
        unique_products = {}
        for p in all_products:
            unique_products[p["ga_product_id"]] = p
        # Overwriting the same ID effectively ensures only one final record per ID
        final_list = list(unique_products.values())

        # Write JSON to data_job/products6.json
        output_directory = os.path.join("data_job")
        os.makedirs(output_directory, exist_ok=True)
        output_file = os.path.join(output_directory, "products6.json")

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(final_list, f, indent=2, ensure_ascii=False)

        self.stdout.write(self.style.SUCCESS(f"Scraped {len(all_products)} raw products."))
        self.stdout.write(self.style.SUCCESS(f"Reduced to {len(final_list)} unique products."))
        self.stdout.write(self.style.SUCCESS(f"Data saved to {output_file}"))
